import typing
from inspect import Parameter

from discord.ext import commands

from const import WEEKDAY_TO_INT
from models.greeter import GreeterType


class BoolConverter(commands.Converter):
    async def convert(self, ctx, argument):
        lowered = argument.lower()
        if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
            return True
        elif lowered in ("no", "n", "false", "f", "0", "disable", "off"):
            return False
        else:
            raise commands.BadArgument(lowered + " is not a recognized boolean option")


class GreeterTypeConverter(commands.Converter):
    async def convert(self, ctx, argument):
        lowered = argument.lower()
        try:
            return GreeterType(lowered)
        except ValueError:
            raise commands.BadArgument(f"Greeter type '{argument}' does not exist")


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
            raise commands.BadArgument(
                "Found neither a reaction string, nor exactly one attachment."
            )


class DayOfWeekConverter(commands.Converter):
    def __init__(self):
        super().__init__()

    async def convert(self, ctx, argument):
        lowered = argument.lower()

        if (weekday_int := WEEKDAY_TO_INT.get(lowered)) is None:
            raise commands.BadArgument(
                f"`{argument}` is not a valid value for the day of the week."
            )
        else:
            return weekday_int

    @staticmethod
    def possible_values():
        return tuple(WEEKDAY_TO_INT.keys())


_old_transform = commands.Command.transform


def _transform(self, ctx, param):
    if param.annotation is ReactionConverter and param.default is param.empty:
        if ctx.message.attachments:
            default = ctx.message.attachments[0].url
            param = Parameter(
                param.name,
                param.kind,
                default=default,
                annotation=typing.Optional[param.annotation],
            )
        else:
            param = Parameter(param.name, param.kind, annotation=param.annotation)

    return _old_transform(self, ctx, param)


commands.Command.transform = _transform
