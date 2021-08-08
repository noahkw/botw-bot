from functools import wraps

from discord.ext import commands

from const import UNICODE_EMOJI


async def _call_help(ctx):
    """Shows help for this group."""
    await ctx.send_help(ctx.command.parent)


def auto_help(func):
    if not isinstance(func, commands.Group):
        raise TypeError("bad deco order")

    cmd = commands.Command(_call_help, name="help", hidden=True)
    func.add_command(cmd)
    return func


def ack(cmd):
    @wraps(cmd)
    async def acked_command(self, ctx, *args, **kwargs):
        await cmd(self, ctx, *args, **kwargs)
        await ctx.message.add_reaction(UNICODE_EMOJI["CHECK"])

    return acked_command
