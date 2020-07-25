import logging
import random

from discord.ext import commands
from discord.utils import find

from const import SHOUT_EMOJI, CHECK_EMOJI
from util import ack, git_version_label

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Utilities(bot))


class Utilities(commands.Cog):
    MOCK_HISTORY_LOOKBACK = 10

    def __init__(self, bot):
        self.bot = bot
        self.bot.version = git_version_label()
        self.shout_emoji = find(lambda e: e.name == SHOUT_EMOJI, self.bot.emojis)

    @commands.command(brief='Displays the bot\'s ping')
    async def ping(self, ctx):
        await ctx.send(
            f'.pong: Discord WebSocket: `{self.bot.latency * 1000:0.2f}` ms')

    @commands.command(brief='Reloads the bot\'s modules')
    @commands.is_owner()
    @ack
    async def reload(self, ctx):
        for ext in self.bot.INITIAL_EXTENSIONS:
            self.bot.reload_extension(ext)

    @commands.command(brief='Makes the bot choose between 2+ things')
    async def choose(self, ctx, *args: commands.clean_content):
        if len(args) < 2:
            await ctx.send('I want at least two things to choose from!')
        else:
            await ctx.send(f'I choose: `{random.choice(args)}`')

    @commands.command(aliases=['v'], brief='Displays the bot\'s version')
    async def version(self, ctx):
        await ctx.send(f'Running version `{self.bot.version}`.')

    @commands.command(brief='Repeats something in uppercase')
    async def shout(self, ctx, *, msg: commands.clean_content):
        await ctx.send(f'{self.shout_emoji} {msg.upper()}!')
