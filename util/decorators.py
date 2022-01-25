import asyncio
import json
from collections import OrderedDict
from functools import wraps

import aiohttp
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


class LeastRecentlyUsed(OrderedDict):
    def __init__(self, size, *args, **kwargs):
        self._size = size
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if len(self) > self._size:
            oldest_key = next(iter(self))
            del self[oldest_key]


class Cached:
    def __init__(self, size: int = 64, ignored_args: list[str] = None):
        self._cache = LeastRecentlyUsed(size)
        self._ignored = ignored_args or []

    def __call__(self, func):
        @wraps(func)
        async def cached_func(*args, **kwargs):
            combined = kwargs.copy()

            for idx, arg in enumerate(args):
                combined[str(idx)] = arg

            for ignored_arg in self._ignored:
                try:
                    combined.pop(ignored_arg)
                except KeyError:
                    pass

            combined_str = json.dumps(combined, sort_keys=True)

            if cached := self._cache.get(combined_str):
                print(cached)
                return cached
            else:
                res = await func(*args, **kwargs)
                self._cache[combined_str] = res
                return res

        return cached_func


async def _test():
    session = aiohttp.ClientSession()

    @Cached(3, ["b"])
    async def make_request(url, **kwargs):
        print("making request to " + url)
        async with session.get(url) as response:
            data = await response.read()

        return data

    await make_request("http://google.com")
    await make_request("http://google.com", a=1, b=1)
    await make_request("http://google.com", a=1, b=2)
    await make_request("http://google.com", a=2, b=3)
    await make_request("http://google.com", a=3, b=4)
    await make_request("http://google.com", a=4, b=5)
    await make_request("http://google.com", a=5, b=6)

    await session.close()


if __name__ == "__main__":
    asyncio.run(_test())
