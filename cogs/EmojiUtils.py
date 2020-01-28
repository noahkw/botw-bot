import logging

import discord
from discord.ext import commands
from util import chunker

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(EmojiUtils(bot))


class EmojiUtils(commands.Cog):
    SPLIT_MSG_AFTER = 15

    def __init__(self, bot):
        self.bot = bot

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
