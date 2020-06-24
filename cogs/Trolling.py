import logging

from discord.ext import commands

from const import CROSS_EMOJI
from util import mock_case, remove_broken_emoji

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Trolling(bot))


class MessageOrStringConverter(commands.IDConverter):
    def __init__(self):
        self.message_converter = commands.MessageConverter()
        super().__init__()

    async def convert(self, ctx, argument):
        try:
            return await self.message_converter.convert(ctx, argument)
        except commands.BadArgument:
            match = self._get_id_match(argument)
            if match is None:
                return str(argument)
            else:
                # argument contains an invalid ID
                raise commands.BadArgument()


class Trolling(commands.Cog):
    MOCK_HISTORY_LOOKBACK = 10

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_listener(self.on_message, 'on_message')
        self.poop_role_name = self.bot.config['trolling']['poop_role_name']

    @commands.command()
    async def mock(self, ctx, *, message: MessageOrStringConverter = None):
        if isinstance(message, str):
            await ctx.send(mock_case(remove_broken_emoji(message)))
        elif message and message.channel == ctx.channel:
            await ctx.send(mock_case(remove_broken_emoji(message.clean_content)))
        else:
            valid_msg_content = None
            async for msg in ctx.message.channel.history(limit=Trolling.MOCK_HISTORY_LOOKBACK):
                msg_ctx = await self.bot.get_context(msg)
                content = remove_broken_emoji(msg.clean_content)
                if msg.author != self.bot.user and not msg_ctx.valid and len(content) > 0:
                    valid_msg_content = content
                    break
            if valid_msg_content and len(valid_msg_content) > 0:
                await ctx.send(mock_case(valid_msg_content))
            else:
                await ctx.message.add_reaction(CROSS_EMOJI)

    @mock.error
    async def mock_error(self, ctx, error):
        if isinstance(error, commands.errors.BadArgument):
            await ctx.send("Can't find message with that ID. It's probably ancient.")
        else:
            logger.exception(error)

    async def on_message(self, message):
        if message.author.bot:
            return

        if self.poop_role_name in [
            role.name for role in message.author.roles
        ]:
            await message.delete()
            await message.channel.send(
                f"{message.author.name}: {mock_case(remove_broken_emoji(message.clean_content))}")
