import asyncio
import json
import logging
from io import BytesIO
from os.path import basename
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import yarl
from aiohttp.typedefs import LooseCookies
from discord import File
from discord.ext import commands
from regex import regex
from yarl import URL

from const import INSPECT_EMOJI
from menu import SimpleConfirm
from util import chunker, auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Instagram(bot))


class InstagramException(Exception):
    pass


class InstagramLoginException(InstagramException):
    pass


class InstagramSpamException(InstagramException):
    pass


class InstagramContentException(InstagramException):
    pass


class OneTimeCookieJar(aiohttp.CookieJar):
    def __init__(
        self, *, unsafe: bool = False, loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> None:
        super().__init__(unsafe=unsafe, loop=loop)
        self._initial_cookies_loaded = False

    def update_cookies(self, cookies: LooseCookies, response_url: URL = URL()) -> None:
        if not self._initial_cookies_loaded:
            super().update_cookies(cookies, response_url)

        self._initial_cookies_loaded = True

    def force_update_cookies(
        self, cookies: LooseCookies, response_url: URL = URL()
    ) -> None:
        super().update_cookies(cookies, response_url)


class Instagram(commands.Cog):
    URL_REGEX = r"https?://(www.)?instagram.com/(p|tv|reel)/(.*?)/"
    FILESIZE_MIN = 10 ** 3
    FILESIZE_MAX = 8 * 10 ** 6  # 8 MB

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(cookie_jar=OneTimeCookieJar())

        self.cookies_file = self.bot.config["cogs"]["instagram"]["cookies_file"]
        with open(self.cookies_file, "r") as f:
            cookies = json.load(f)

        self.session.cookie_jar.update_cookies(cookies=cookies)

        logger.info(f"Loaded {len(self.session.cookie_jar)} cookies")

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    async def get_media(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0",
        }

        params = {"__a": 1}

        async with self.session.get(url, params=params, headers=headers) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                raise InstagramLoginException

            if "spam" in data:
                raise InstagramSpamException
            elif "graphql" not in data:
                raise InstagramContentException

            data = data["graphql"]["shortcode_media"]

        media_type = data["__typename"]

        if media_type == "GraphImage":
            return [data["display_url"]]
        elif media_type == "GraphVideo":
            return [data["video_url"]]
        else:
            media = data["edge_sidecar_to_children"]["edges"]
            return [
                media["node"]["display_url"]
                if media["node"]["__typename"] == "GraphImage"
                else media["node"]["video_url"]
                for media in media
            ]

    async def show_media(self, ctx, url):
        try:
            media = await self.get_media(url)
        except InstagramSpamException:
            raise commands.BadArgument(
                "We are being rate limited by Instagram. Try again later."
            )
        except InstagramContentException:
            raise commands.BadArgument(
                "This Instagram post contains no images or videos."
            )
        except InstagramLoginException:
            owner = self.bot.get_user(self.bot.CREATOR_ID)
            await owner.send(f"Instagram broke! Msg: {ctx.message.jump_url}")
            raise commands.BadArgument(
                "Instagram broke :poop: Bot owner has been notified."
            )

        urls = []
        files = []

        for url in media:
            async with self.session.get(yarl.URL(url, encoded=True)) as response:
                filename = basename(urlparse(url).path)
                bytes = BytesIO(await response.read())

                filesize = bytes.getbuffer().nbytes
                if self.FILESIZE_MIN < filesize < self.FILESIZE_MAX:
                    files.append(File(bytes, filename=filename))
                else:
                    urls.append(url)

        # remove discord's default instagram embed
        await ctx.message.edit(suppress=True)

        url_chunks = chunker(urls, 5)
        for chunk in url_chunks:
            await ctx.send("\n".join(chunk))

        file_chunks = chunker(files, 10)
        for chunk in file_chunks:
            await ctx.send(files=chunk)

    @auto_help
    @commands.group(
        aliases=["ig"],
        invoke_without_command=True,
        brief="Display posts from Instagram",
    )
    async def instagram(self, ctx, args=None):
        if args:
            await ctx.invoke(self.show, url=args)
        else:
            await ctx.send_help(self.instagram)

    @instagram.command()
    async def show(self, ctx, url):
        result = regex.match(self.URL_REGEX, url)
        if result:
            url = result.group(0)
        else:
            raise commands.BadArgument("Invalid Instagram URL.")

        await self.show_media(ctx, url)

    @instagram.command()
    @commands.is_owner()
    async def reload(self, ctx):
        with open(self.cookies_file, "r") as f:
            cookies = json.load(f)

        self.session.cookie_jar.force_update_cookies(cookies=cookies)

        await ctx.send(f"Loaded {len(self.session.cookie_jar)} cookies")

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)
        if ctx.valid or not ctx.guild or message.webhook_id:
            return

        results = regex.finditer(self.URL_REGEX, message.content)
        urls = [result.group(0) for result in results]

        if len(urls) > 0:
            confirm = await SimpleConfirm(message, emoji=INSPECT_EMOJI).prompt(ctx)
            if confirm:
                async with ctx.typing():
                    for url in urls:
                        try:
                            await self.show_media(ctx, url)
                        except commands.BadArgument as error:
                            await ctx.send(error)

    async def cog_before_invoke(self, ctx):
        await ctx.trigger_typing()
