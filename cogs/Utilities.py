import logging
import random
import subprocess

from discord import Message
from discord.ext import commands
from discord.utils import find, escape_mentions

from const import SHOUT_EMOJI, CROSS_EMOJI
from util import mock_case, remove_broken_emoji

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Utilities(bot))


class Utilities(commands.Cog):
    MOCK_HISTORY_LOOKBACK = 10

    def __init__(self, bot):
        self.bot = bot
        self.shout_emoji = find(lambda e: e.name == SHOUT_EMOJI,
                                self.bot.emojis)

    @commands.command()
    async def ping(self, ctx):
        await ctx.send(
            f'.pong: Discord WebSocket: `{self.bot.latency * 1000:0.2f}` ms')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reload(self, ctx):
        self.bot.reload_extension('cogs.BiasOfTheWeek')
        self.bot.reload_extension('cogs.Utilities')
        self.bot.reload_extension('cogs.Scheduler')
        self.bot.reload_extension('cogs.EmojiUtils')
        self.bot.reload_extension('cogs.Tags')
        self.bot.reload_extension('cogs.WolframAlpha')

    @reload.error
    async def reload_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingPermissions):
            await ctx.send(error)
        logger.error(error)

    @commands.command()
    async def choose(self, ctx, *args: commands.clean_content):
        if len(args) < 2:
            await ctx.send('I want at least two things to choose from!')
        else:
            await ctx.send(f'I choose: `{random.choice(args)}`')

    @commands.command(aliases=['v'])
    async def version(self, ctx):
        label = subprocess.check_output(
            ['git', 'describe', '--tags', '--long']).decode('ascii').strip()
        await ctx.send(f'Running version `{label}`.')

    @commands.command()
    async def shout(self, ctx, *, msg: commands.clean_content):
        await ctx.send(f'{self.shout_emoji} {msg.upper()}!')

    @shout.error
    async def shout_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingRequiredArgument):
            await ctx.send('Give me something to shout!')

    @commands.command()
    async def mock(self, ctx, message: Message = None):
        if message:
            await ctx.send(mock_case(remove_broken_emoji(message.clean_content)))
        else:
            valid_msg = None
            async for msg in ctx.message.channel.history(limit=Utilities.MOCK_HISTORY_LOOKBACK):
                msg_ctx = await self.bot.get_context(msg)
                if msg.author != self.bot.user and not msg_ctx.valid:
                    valid_msg = msg
                    break
            if valid_msg is not None:
                await ctx.send(mock_case(remove_broken_emoji(valid_msg.clean_content)))
            else:
                await ctx.message.add_reaction(CROSS_EMOJI)
