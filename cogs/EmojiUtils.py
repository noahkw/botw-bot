import asyncio
import logging
import typing
from pathlib import Path

import aiohttp
import discord
import pendulum
from discord.ext import commands
from sqlalchemy.exc import NoResultFound

import db
from menu import Confirm
from models import EmojiSettings
from util import chunker, Cooldown, auto_help, format_emoji

logger = logging.getLogger(__name__)


async def setup(bot):
    await bot.add_cog(EmojiUtils(bot))


class EmojiUtils(commands.Cog):
    SPLIT_MSG_AFTER = 15
    SPLIT_STICKERS_AFTER = 3
    NEW_EMOTE_THRESHOLD = 60  # in minutes
    DELETE_LIMIT = 50
    UPDATE_FREQUENCY = 60  # in seconds

    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}  # guild.id -> cooldown
        self.last_updates = {}  # guild.id -> on_guild_emojis_update after obj
        self.session = aiohttp.ClientSession()

        EmojiSettings.inject_bot(bot)

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    async def _send_emoji_list(self, channel: discord.TextChannel, after=None):
        emojis = after if after else channel.guild.emojis
        emoji_sorted = sorted(emojis, key=lambda e: e.name)
        for emoji_chunk in chunker(emoji_sorted, self.SPLIT_MSG_AFTER):
            await channel.send(" ".join(str(e) for e in emoji_chunk))

    async def _send_sticker_list(self, channel: discord.TextChannel):
        stickers = channel.guild.stickers
        stickers_sorted = sorted(stickers, key=lambda s: s.name)

        for sticker_chunk in chunker(stickers_sorted, self.SPLIT_STICKERS_AFTER):
            await channel.send(stickers=sticker_chunk)

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

    async def _download_emoji(self, emoji_url):
        async with self.session.get(emoji_url) as response:
            if response.status != 200:
                raise commands.BadArgument("Could not fetch the given URL.")

            return await response.read()

    @auto_help
    @commands.group(
        name="sticker",
        brief="Sticker related convenience commands",
    )
    @commands.has_permissions(manage_emojis=True)
    async def sticker(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.sticker)

    @sticker.command(name="list", brief="Sends a list of the guild's stickers")
    async def sticker_list(self, ctx, channel: discord.TextChannel = None):
        await self._send_sticker_list(channel or ctx.channel)

    @auto_help
    @commands.group(
        name="emoji",
        brief="Emoji related convenience commands",
    )
    @commands.has_permissions(manage_emojis=True)
    async def emoji(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.emoji)

    @emoji.command(name="add", brief="Adds a custom emoji")
    @commands.cooldown(1, per=5, type=commands.BucketType.user)
    @commands.bot_has_permissions(manage_emojis=True)
    async def emoji_add(
        self,
        ctx,
        name: str = None,
        reaction_attachment: typing.Optional[discord.Attachment] = None,
        *,
        reaction_text: typing.Optional[commands.clean_content] = "",
    ):
        emoji = reaction_attachment or reaction_text or name

        if type(emoji) is discord.Attachment:
            emoji_bytes = await emoji.read()
            name = name or Path(emoji.filename).stem
        elif type(emoji) is str:
            try:
                emoji_bytes = await asyncio.wait_for(self._download_emoji(emoji), 5.0)
            except asyncio.TimeoutError:
                logger.warning(
                    "Emoji URL download timed out. User %s (%s); URL %s",
                    str(ctx.author),
                    ctx.author.id,
                    emoji,
                )
                raise commands.BadArgument("Download timed out.")

            name = name if name != emoji else Path(emoji).stem
        else:
            raise commands.BadArgument("Attach an image file or a URL.")

        try:
            custom_emoji = await ctx.guild.create_custom_emoji(
                name=name, image=emoji_bytes, reason=f"Added by {ctx.author}"
            )
        except discord.HTTPException as e:
            logger.exception("Emoji upload failed for URL %s", emoji)
            raise commands.BadArgument("Error " + e.text.split("\n")[-1])
        except discord.InvalidArgument:
            raise commands.BadArgument(
                "Bad image file. Must be either JPG, PNG, or GIF."
            )

        await ctx.send(
            f"Added custom emoji {custom_emoji} with name `{custom_emoji.name}`."
        )

    @emoji.command(
        name="remove",
        brief="Removes one or multiple custom emoji",
        aliases=["delete", "rm"],
    )
    @commands.bot_has_permissions(manage_emojis=True)
    async def emoji_remove(self, ctx, *emojis: commands.EmojiConverter):
        emojis_formatted = "\n".join(format_emoji(emoji) for emoji in emojis)
        for emoji in emojis:
            if emoji.guild != ctx.guild:
                raise commands.BadArgument(f"{emoji} is in another guild.")
        confirm = await Confirm(
            f"Are you sure you want to remove the following emoji?\n{emojis_formatted}"
        ).prompt(ctx)

        if confirm:
            emoji_names = ", ".join(f"`{emoji.name}`" for emoji in emojis)
            await asyncio.gather(
                *[emoji.delete(reason=f"Deleted by {ctx.author}") for emoji in emojis]
            )
            await ctx.send(f"Deleted emoji {emoji_names}.")

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
