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
