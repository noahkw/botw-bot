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
        self.emoji_channel = self.bot.get_channel(int(self.bot.config['emojiutils']['emoji_channel']))
        self.lock = asyncio.Lock()
        self.cooldown = Cooldown(self.UPDATE_FREQUENCY)
        self.last_update = None

    @commands.group(name='emoji')
    @commands.has_permissions(administrator=True)
    async def emoji(self, ctx):
        pass

    @emoji.command(name='list')
    async def emoji_list(self, ctx, channel: discord.TextChannel):
        await self.send_emoji_list(channel)

    @commands.Cog.listener('on_guild_emojis_update')
    async def on_guild_emojis_update(self, guild, before, after):
        self.last_update = after

        if self.cooldown.cooldown:
            return
        else:
            async with self.cooldown:
                await self.update_emoji_list()

    async def send_emoji_list(self, channel):
        emoji_sorted = sorted(channel.guild.emojis, key=lambda e: e.name)
        for emoji_chunk in chunker(emoji_sorted, EmojiUtils.SPLIT_MSG_AFTER):
            await channel.send(' '.join(str(e) for e in emoji_chunk))

    async def update_emoji_list(self):
        async with self.lock:
            # delete old messages containing emoji
            # need to use Message.delete to be able to delete messages older than 14 days
            async for message in self.emoji_channel.history(limit=EmojiUtils.DELETE_LIMIT):
                await message.delete()

            # get emoji that were added in the last 10 minutes
            now = pendulum.now('UTC')
            recent_emoji = [emoji for emoji in self.last_update if now.diff(pendulum.instance(
                discord.utils.snowflake_time(emoji.id))).in_minutes() < EmojiUtils.NEW_EMOTE_THRESHOLD]

            await self.send_emoji_list(self.emoji_channel)

            if len(recent_emoji) > 0:
                await self.emoji_channel.send(f"Recently added: {''.join(str(e) for e in recent_emoji)}")
