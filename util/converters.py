import typing
from inspect import Parameter

from discord.ext import commands


class BoolConverter(commands.Converter):
    async def convert(self, ctx, argument):
        lowered = argument.lower()
        if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
            return True
        elif lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
            return False
        else:
            raise commands.BadArgument(lowered + ' is not a recognized boolean option')


class ReactionConverter(commands.Converter):
    def __init__(self):
        super().__init__()
        self.clean_content = commands.clean_content()

    async def convert(self, ctx, argument):
        # default value of using the first attachment is handled in the 'hijacked' transform method below
        if len(argument) > 0:
            # string supplied, just escape and return it
            return await self.clean_content.convert(ctx, argument)
        else:
            raise commands.BadArgument('Found neither a reaction string, nor exactly one attachment.')


_old_transform = commands.Command.transform


def _transform(self, ctx, param):
    if param.annotation is ReactionConverter and param.default is param.empty:
        if ctx.message.attachments:
            default = ctx.message.attachments[0].url
            param = Parameter(param.name, param.kind, default=default, annotation=typing.Optional[param.annotation])
        else:
            param = Parameter(param.name, param.kind, annotation=param.annotation)

    return _old_transform(self, ctx, param)


commands.Command.transform = _transform