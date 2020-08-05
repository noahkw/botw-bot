import asyncio
import logging

from discord.ext import commands
from discord.ext.menus import MenuPages
from gfypy import AsyncGfypy

from menu import GfyListSource
from util import auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Gfycat(bot))


class Gfycat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gfypy = AsyncGfypy(self.bot.config['gfycat']['client_id'],
                                self.bot.config['gfycat']['client_secret'],
                                '../gfycat_creds.json')

    def cog_unload(self):
        asyncio.create_task(self.gfypy.close())

    @auto_help
    @commands.group(aliases=['gfy'], invoke_without_command=True, brief='Display content from Gfycat')
    async def gfycat(self, ctx):
        await ctx.send_help(self.gfycat)

    async def send_gfy_list(self, ctx, gfys, user_id):
        await ctx.send(f'Found `{len(gfys)}` Gfys for user `{user_id}`.')
        pages = MenuPages(source=GfyListSource(gfys), clear_reactions_after=True)
        await pages.start(ctx)

    @gfycat.command()
    async def list(self, ctx, user_id):
        with ctx.typing():
            gfys = await self.gfypy.get_user_feed(user_id, limit=-1)

        await self.send_gfy_list(ctx, gfys, user_id)

    @gfycat.command()
    async def top(self, ctx, user_id):
        with ctx.typing():
            gfys = await self.gfypy.get_user_feed(user_id, limit=-1, sort_by='views')

        await self.send_gfy_list(ctx, gfys, user_id)

    async def cog_before_invoke(self, ctx):
        await ctx.trigger_typing()
