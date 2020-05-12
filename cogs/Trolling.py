import logging

from discord import Message
from discord.ext import commands

from const import CROSS_EMOJI
from util import mock_case, remove_broken_emoji

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Trolling(bot))


class Trolling(commands.Cog):
    MOCK_HISTORY_LOOKBACK = 10

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mock(self, ctx, message: Message = None):
        if message:
            if message.channel == ctx.channel:
                await ctx.send(mock_case(remove_broken_emoji(message.clean_content)))
            else:
                await ctx.message.add_reaction(CROSS_EMOJI)
        else:
            valid_msg_content = None
            async for msg in ctx.message.channel.history(limit=Trolling.MOCK_HISTORY_LOOKBACK):
                msg_ctx = await self.bot.get_context(msg)
                content = remove_broken_emoji(msg.clean_content)
                if msg.author != self.bot.user and not msg_ctx.valid and len(content) > 0:
                    valid_msg_content = content
                    break
            if valid_msg_content is not None:
                await ctx.send(mock_case(valid_msg_content))
            else:
                await ctx.message.add_reaction(CROSS_EMOJI)

    @mock.error
    async def mock_error(self, ctx, error):
        if isinstance(error, commands.errors.BadArgument):
            await ctx.send("Can't find message with that ID. It's probably ancient.")
