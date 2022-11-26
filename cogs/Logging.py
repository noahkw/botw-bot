import logging
from functools import wraps

from discord.ext import commands
from discord.ext.menus import MenuPages

import db
from menu import CommandUsageListSource
from models import CommandLog


def log_usage(command_name=None, log_args=True):
    def deco(func):
        @wraps(func)
        async def logged_func(self, ctx, *args, **kwargs):
            async with self.bot.Session() as session:
                arg_list = args if log_args else []
                session.add(
                    CommandLog(
                        command_name=command_name or func.__name__,
                        cog=type(self).__name__,
                        _user=ctx.author.id,
                        _guild=ctx.guild.id if ctx.guild else None,
                        args=", ".join(
                            [repr(arg) for arg in arg_list]
                            + [f"{k}={str(v)}" for k, v in kwargs.items()]
                        ),
                    )
                )
                await session.commit()

            await func(self, ctx, *args, **kwargs)

        return logged_func

    return deco


logger = logging.getLogger(__name__)


async def setup(bot):
    await bot.add_cog(Logging(bot))


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        CommandLog.inject_bot(bot)

    @commands.group()
    @commands.is_owner()
    async def usage(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.usage)

    @usage.command(name="command", aliases=["cmd"])
    async def usage_command(
        self, ctx, command_name: str, by: str = "user", weeks: int = 1
    ):
        async with self.bot.Session() as session:
            usages = await db.get_command_usage_by(session, by, command_name, weeks)

            if len(usages) > 0:
                pages = MenuPages(
                    source=CommandUsageListSource(usages, by, command_name, weeks),
                    clear_reactions_after=True,
                )
                await pages.start(ctx)
            else:
                await ctx.send(
                    f"No usages for command `{command_name}` in the given time frame."
                )
