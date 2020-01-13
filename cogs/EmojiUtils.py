import logging
import discord

from itertools import zip_longest

from discord.ext import commands

logger = logging.getLogger('discord')


def grouper(iterable, n, fillvalue=''):
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def setup(bot):
    bot.add_cog(EmojiUtils(bot))


class EmojiUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.split_msg_after = 15

    @commands.group(name='emoji')
    @commands.has_permissions(administrator=True)
    async def emoji(self, ctx):
        pass

    @emoji.command(name='list')
    async def emoji_list(self, ctx, channel: discord.TextChannel):
        emoji_sorted = sorted(ctx.guild.emojis, key=lambda e: e.name)
        for emoji_chunk in grouper(emoji_sorted, self.split_msg_after):
            await channel.send(' '.join(str(e) for e in emoji_chunk))

    @emoji_list.error
    async def emoji_list_error(self, ctx, error):
        await ctx.send(error)
