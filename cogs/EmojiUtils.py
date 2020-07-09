import asyncio
import logging

import discord
import pendulum
from discord.ext import commands

from util import chunker, Cooldown

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
        self.cooldowns = {}
        self.last_updates = {}

    @commands.group(name='emoji')
    @commands.has_permissions(administrator=True)
    async def emoji(self, ctx):
        pass

    @emoji.command(name='list')
    async def emoji_list(self, ctx, channel: discord.TextChannel):
        await self.send_emoji_list(channel)

    @commands.Cog.listener('on_guild_emojis_update')
    async def on_guild_emojis_update(self, guild, before, after):
        self.last_updates[guild] = after

        if guild not in self.cooldowns:
            self.cooldowns[guild] = Cooldown(self.UPDATE_FREQUENCY)

        if self.cooldowns[guild].cooldown:
            return
        else:
            async with self.cooldowns[guild]:
                await self.update_emoji_list(guild)

    async def send_emoji_list(self, channel, after=None):
        emojis = after if after else channel.guild.emojis
        emoji_sorted = sorted(emojis, key=lambda e: e.name)
        for emoji_chunk in chunker(emoji_sorted, self.SPLIT_MSG_AFTER):
            await channel.send(' '.join(str(e) for e in emoji_chunk))

    async def update_emoji_list(self, guild):
        settings_cog = self.bot.get_cog('Settings')
        settings = await settings_cog.get_settings(guild)
        emoji_channel = settings.emoji_channel.value
        if emoji_channel is None:
            logger.warning(f'Emoji channel for guild {guild} is not set. Skipping update')
            return

        # delete old messages containing emoji
        # need to use Message.delete to be able to delete messages older than 14 days
        async for message in emoji_channel.history(limit=self.DELETE_LIMIT):
            await message.delete()

        # get emoji that were added in the last NEW_EMOTE_THRESHOLD minutes
        now = pendulum.now('UTC')
        recent_emoji = [emoji for emoji in self.last_updates[guild] if now.diff(pendulum.instance(
            discord.utils.snowflake_time(emoji.id))).in_minutes() < self.NEW_EMOTE_THRESHOLD]

        await self.send_emoji_list(emoji_channel, after=self.last_updates[guild])

        if len(recent_emoji) > 0:
            await emoji_channel.send(f"Recently added: {''.join(str(e) for e in recent_emoji)}")
