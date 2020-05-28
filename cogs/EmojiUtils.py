import logging
import time

import discord
from discord.ext import commands

from util import chunker

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(EmojiUtils(bot))


class EmojiUtils(commands.Cog):
    SPLIT_MSG_AFTER = 15
    NEW_EMOTE_THRESHOLD = 3600 + 600  # 3600 + number of seconds
    DELETE_LIMIT = 50

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_listener(self.on_guild_emojis_update, 'on_guild_emojis_update')
        self.emoji_channel = self.bot.get_channel(int(self.bot.config['emojiutils']['emoji_channel']))

    @commands.group(name='emoji')
    @commands.has_permissions(administrator=True)
    async def emoji(self, ctx):
        pass

    @emoji.command(name='list')
    async def emoji_list(self, ctx, channel: discord.TextChannel):
        emoji_sorted = sorted(ctx.guild.emojis, key=lambda e: e.name)
        for emoji_chunk in chunker(emoji_sorted, EmojiUtils.SPLIT_MSG_AFTER):
            await channel.send(' '.join(str(e) for e in emoji_chunk))

    @emoji_list.error
    async def emoji_list_error(self, ctx, error):
        await ctx.send(error)

    async def on_guild_emojis_update(self, guild, before, after):
        # delete old messages containing emoji
        # need to use Message.delete to be able to delete messages older than 14 days
        async for message in self.emoji_channel.history(limit=EmojiUtils.DELETE_LIMIT):
            await message.delete()

        # get emoji that were added in the last 10 minutes
        recent_emoji = [emoji for emoji in after if time.time() - discord.utils.snowflake_time(
            emoji.id).timestamp() < EmojiUtils.NEW_EMOTE_THRESHOLD]

        emoji_sorted = sorted(after, key=lambda e: e.name)
        for emoji_chunk in chunker(emoji_sorted, EmojiUtils.SPLIT_MSG_AFTER):
            await self.emoji_channel.send(''.join(str(e) for e in emoji_chunk))

        if len(recent_emoji) > 0:
            await self.emoji_channel.send(f"Newly added: {''.join(str(e) for e in recent_emoji)}")
