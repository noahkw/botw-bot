import asyncio
import logging

import typing
from discord.ext import commands
from discord.ext.menus import MenuPages
from gfypy import AsyncGfypy

from menu import GfyListSource, AsyncGfySource, GfySourceEmpty
from util import auto_help, DNFParser

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Gfycat(bot))


class AsyncGenFilter:
    def __init__(self, aiterable, predicate):
        self.aiterable = aiterable
        self.predicate = predicate

    def __aiter__(self):
        return self

    async def __anext__(self):
        while payload := await self.aiterable.__anext__():
            if self.predicate(payload):
                return payload


class SortByConverter(commands.Converter):
    OPTIONS = ('views', 'likes',)

    async def convert(self, ctx, argument):
        if argument in self.OPTIONS:
            return argument

        raise commands.BadArgument(f'Can\'t sort by {argument}. Possible values: `{", ".join(self.OPTIONS)}`')


class Gfycat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gfypy = AsyncGfypy(self.bot.config['gfycat']['client_id'],
                                self.bot.config['gfycat']['client_secret'],
                                '../gfycat_creds.json')

    def cog_unload(self):
        asyncio.create_task(self.gfypy.close())

    async def _start_gfy_pagination(self, ctx, source, user_id):
        if type(source) is list:
            await ctx.send(f'Found `{len(source)}` Gfys for user `{user_id}`.')
            source = GfyListSource(source)
        else:
            source = AsyncGfySource(source)

        pages = MenuPages(source=source, clear_reactions_after=True)
        try:
            await pages.start(ctx)
        except GfySourceEmpty:
            await ctx.send('Could not find any gfys that meet the given criteria.')

    @auto_help
    @commands.group(aliases=['gfy'], invoke_without_command=True, brief='Display content from Gfycat')
    async def gfycat(self, ctx):
        await ctx.send_help(self.gfycat)

    @gfycat.command()
    async def list(self, ctx, user_id, sort_by: typing.Optional[SortByConverter] = None):
        with ctx.typing():
            if sort_by:
                gfys = await self.gfypy.get_user_feed(user_id=user_id, limit=-1, sort_by=sort_by)
            else:
                gfys = self.gfypy.user_feed_generator(user_id=user_id)

        await self._start_gfy_pagination(ctx, gfys, user_id)

    @gfycat.command()
    async def top(self, ctx, user_id):
        await ctx.invoke(self.list, user_id, sort_by='views')

    @gfycat.command(brief='Search an account by tags')
    async def search(self, ctx, user_id, sort_by: typing.Optional[SortByConverter] = None, *, query):
        parser = DNFParser(query)

        with ctx.typing():
            if sort_by:
                gfys = await self.gfypy.get_user_feed(user_id=user_id, limit=-1, sort_by=sort_by)
                gfys = list(filter(lambda gfy: parser.evaluate(gfy.tags), gfys))
            else:
                gfys = self.gfypy.user_feed_generator(user_id=user_id, per_request=20)
                gfys = AsyncGenFilter(gfys, lambda gfy: parser.evaluate(gfy.tags))

        await self._start_gfy_pagination(ctx, gfys, user_id)

    async def cog_before_invoke(self, ctx):
        await ctx.trigger_typing()
