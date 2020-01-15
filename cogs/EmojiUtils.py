import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


def chunker(iterable, n):
    """
    Produces a generator that yields chunks of given size from an iterator.
    :param iterable: iterable to generate chunks from
    :param n: number of items in each chunk
    :return: the individual chunks
    """
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]


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
