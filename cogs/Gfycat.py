import asyncio
import logging
import typing
from io import BytesIO

import discord
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from discord.ext import commands
from discord.ext.menus import MenuPages
from gfypy import AsyncGfypy
from gfypy.const import GFYCAT_URL

from cogs import CustomCog, AinitMixin
from menu import GfyListSource, AsyncGfySource, GfySourceEmpty
from util import auto_help, DNFParser

logger = logging.getLogger(__name__)


async def setup(bot):
    await bot.add_cog(Gfycat(bot))


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
    OPTIONS = (
        "views",
        "likes",
    )

    async def convert(self, ctx, argument):
        if argument in self.OPTIONS:
            return argument

        raise commands.BadArgument(
            f'Can\'t sort by {argument}. Possible values: `{", ".join(self.OPTIONS)}`'
        )


class Gfycat(CustomCog, AinitMixin):
    def __init__(self, bot):
        super().__init__(bot)
        self.gfypy = AsyncGfypy(
            self.bot.config["cogs"]["gfycat"]["client_id"],
            self.bot.config["cogs"]["gfycat"]["client_secret"],
            "gfycat_creds.json",
        )

        super(AinitMixin).__init__()

    async def _ainit(self):
        pass
        # await self.gfypy.authenticate()

    def cog_unload(self):
        asyncio.create_task(self.gfypy.close())

    async def _start_gfy_pagination(self, ctx, source, user_id):
        if type(source) is list:
            await ctx.send(f"Found `{len(source)}` Gfys for user `{user_id}`.")
            source = GfyListSource(source)
        else:
            source = AsyncGfySource(source)

        pages = MenuPages(source=source, clear_reactions_after=True)
        try:
            await pages.start(ctx)
        except GfySourceEmpty:
            await ctx.send("Could not find any gfys that meet the given criteria.")

    @auto_help
    @commands.group(
        aliases=["gfy"],
        brief="Display content from Gfycat",
    )
    async def gfycat(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.gfycat)

    @gfycat.command()
    async def list(
        self, ctx, user_id, sort_by: typing.Optional[SortByConverter] = None
    ):
        with ctx.typing():
            if sort_by:
                gfys = await self.gfypy.get_user_feed(
                    user_id=user_id, limit=-1, sort_by=sort_by
                )
            else:
                gfys = self.gfypy.user_feed_generator(user_id=user_id)

        await self._start_gfy_pagination(ctx, gfys, user_id)

    @gfycat.command()
    async def top(self, ctx, user_id):
        await ctx.invoke(self.list, user_id, sort_by="views")

    @gfycat.command(brief="Search an account by tags")
    async def search(
        self, ctx, user_id, sort_by: typing.Optional[SortByConverter] = None, *, query
    ):
        parser = DNFParser(query)

        with ctx.typing():
            if sort_by:
                gfys = await self.gfypy.get_user_feed(
                    user_id=user_id, limit=-1, sort_by=sort_by
                )
                gfys = list(filter(lambda gfy: parser.evaluate(gfy.tags), gfys))
            else:
                gfys = self.gfypy.user_feed_generator(user_id=user_id, per_request=20)
                gfys = AsyncGenFilter(gfys, lambda gfy: parser.evaluate(gfy.tags))

        await self._start_gfy_pagination(ctx, gfys, user_id)

    @gfycat.command(
        brief="Display the search in a nice-to-copy-paste format", hidden=True
    )
    async def format(self, ctx, *, query):
        parser = DNFParser(query)

        with ctx.typing():
            gfys = await self.gfypy.get_own_feed()
            gfys = list(filter(lambda gfy: parser.evaluate(gfy.tags), gfys))

        if len(gfys) == 0:
            raise commands.BadArgument(
                "Could not find any gfys that meet the given criteria."
            )

        title = gfys[0].title.split("-")[0].strip()

        links = map(lambda gfy: f"{GFYCAT_URL}/{gfy.gfy_id}", gfys)
        formatted = f"````{title}`\n" + "\n".join(links) + "```"

        await ctx.send(formatted)

    @gfycat.command(brief="Display the number of views in a diagram")
    async def plot(
        self,
        ctx,
        user_id,
        filter_outliers: typing.Optional[bool] = False,
        start: int = None,
        end: int = None,
    ):
        with ctx.typing():
            gfys = await self.gfypy.get_user_feed(user_id=user_id, limit=-1)

            data = [
                (int(gfy.create_date.strftime("%y%m%d")), gfy.views) for gfy in gfys
            ]
            data = pd.DataFrame(data, columns=["date", "views"])

            if filter_outliers:
                data = data[data.views <= data.views.quantile(0.85)]

            if start and end:
                data = data[(data.date >= start) & (data.date <= end)]

            if len(data) == 0:
                raise commands.BadArgument(
                    "Could not find any gfys that meet the given criteria."
                )

            mean = data.mean()["views"]
            data = data.groupby("date").mean()
            data.reset_index(inplace=True)

            sns.set(rc={"figure.figsize": (30, 20)})
            plt.figure()
            g = sns.barplot(data=data, x="date", y="views")
            g.locator_params(nbins=9, axis="x")

            buf = BytesIO()
            plt.savefig(buf, format="png", dpi=200, bbox_inches="tight")
            buf.seek(0)

            await ctx.send(
                f"{ctx.author.mention}, here's the diagram. Average views per gfy"
                f" in the selected timeframe: `{mean:.2f}`.",
                file=discord.File(buf, filename="gfycat_views.png"),
            )

    async def cog_before_invoke(self, ctx):
        await ctx.trigger_typing()
