import logging

import discord
import pendulum
from discord.ext import commands
from sqlalchemy.exc import NoResultFound

import db
from models import EmojiSettings
from util import chunker, Cooldown, auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(EmojiUtils(bot))


class EmojiUtils(commands.Cog):
    SPLIT_MSG_AFTER = 15
    NEW_EMOTE_THRESHOLD = 60  # in minutes
    DELETE_LIMIT = 50
    UPDATE_FREQUENCY = 60  # in seconds

    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}  # guild.id -> cooldown
        self.last_updates = {}  # guild.id -> on_guild_emojis_update after obj

        EmojiSettings.inject_bot(bot)

    async def _send_emoji_list(self, channel: discord.TextChannel, after=None):
        emojis = after if after else channel.guild.emojis
        emoji_sorted = sorted(emojis, key=lambda e: e.name)
        for emoji_chunk in chunker(emoji_sorted, self.SPLIT_MSG_AFTER):
            await channel.send(" ".join(str(e) for e in emoji_chunk))

    async def _update_emoji_list(self, guild: discord.Guild):
        async with self.bot.Session() as session:
            try:
                emoji_settings = await db.get_emoji_settings(session, guild.id)
            except NoResultFound:
                logger.warning(
                    f"Emoji channel for guild {guild} is not set. Skipping update"
                )
                return

            emoji_channel = emoji_settings.channel

            # delete old messages containing emoji
            # need to use Message.delete to be able to delete messages older than 14 days
            async for message in emoji_channel.history(limit=self.DELETE_LIMIT):
                await message.delete()

            # get emoji that were added in the last NEW_EMOTE_THRESHOLD minutes
            now = pendulum.now("UTC")
            recent_emoji = [
                emoji
                for emoji in self.last_updates[guild.id]
                if now.diff(
                    pendulum.instance(discord.utils.snowflake_time(emoji.id))
                ).in_minutes()
                < self.NEW_EMOTE_THRESHOLD
            ]

            await self._send_emoji_list(
                emoji_channel, after=self.last_updates[guild.id]
            )

            if len(recent_emoji) > 0:
                await emoji_channel.send(
                    f"Recently added: {''.join(str(e) for e in recent_emoji)}"
                )

    @auto_help
    @commands.group(
        name="emoji",
        brief="Emoji related convenience commands",
    )
    @commands.has_permissions(manage_emojis=True)
    async def emoji(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.emoji)

    @emoji.command(name="list", brief="Sends a list of the guild's emoji")
    async def emoji_list(self, ctx, channel: discord.TextChannel = None):
        await self._send_emoji_list(channel or ctx.channel)

    @emoji.command(name="channel", brief="Configures given channel for emoji updates")
    @commands.has_permissions(manage_guild=True)
    async def channel(self, ctx, channel: discord.TextChannel):
        """
        Configures the given channel for emoji updates.
        The bot will automatically keep an up-to-date list of emoji in this channel.

        **Caution**: The bot will delete old messages in the channel, so
        it is best to create a channel dedicated to showcasing emoji.
        """
        async with self.bot.Session() as session:
            emoji_settings = EmojiSettings(_guild=ctx.guild.id, _channel=channel.id)
            await session.merge(emoji_settings)
            await session.commit()

        await ctx.send(f"{channel.mention} will now receive emoji updates.")

    @commands.Cog.listener("on_guild_emojis_update")
    async def on_guild_emojis_update(self, guild, before, after):
        self.last_updates[guild.id] = after

        if guild.id not in self.cooldowns:
            self.cooldowns[guild.id] = Cooldown(self.UPDATE_FREQUENCY)

        if self.cooldowns[guild.id].cooldown:
            return
        else:
            async with self.cooldowns[guild.id]:
                await self._update_emoji_list(guild)
