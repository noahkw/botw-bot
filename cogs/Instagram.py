import abc
import asyncio
import collections
import dataclasses
import json
import logging
import typing
from io import BytesIO
from os.path import basename
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import discord
import yarl
from aiohttp.typedefs import LooseCookies
from discord import File
from discord.ext import commands
from regex import regex
from yarl import URL

from cogs.Logging import log_usage
from const import UNICODE_EMOJI
from menu import SimpleConfirm
from util import (
    chunker,
    auto_help,
    ReactingRetryingSession,
    ExceededMaximumRetries,
    LeastRecentlyUsed,
)

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


class InstagramExtractor:
    @abc.abstractmethod
    def extract_media(self, data: dict) -> list[str]:
        pass


class InstagramExtractorV1(InstagramExtractor):
    def extract_media(self, data: dict) -> list[str]:
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


class InstagramExtractorV2(InstagramExtractor):
    """
    Needed since Instagram made changes to their GraphQL API on 2021-01-19.
    """

    def extract_media(self, data: dict) -> list[str]:
        if "spam" in data:
            raise InstagramSpamException
        elif not (media_items := data.get("items")) or len(media_items) < 1:
            raise InstagramContentException

        media_items = media_items[0]
        media_items = media_items.get("carousel_media") or [media_items]

        urls = []

        for item in media_items:
            versions = (
                item.get("video_versions") or item["image_versions2"]["candidates"]
            )
            urls.append(versions[0]["url"])

        return urls


FileStub = collections.namedtuple("FileStub", "filename bytes")


@dataclasses.dataclass
class IGPostResult:
    urls: list[str] = dataclasses.field(default_factory=list)
    files: list[FileStub] = dataclasses.field(default_factory=list)
    exceptions: list[ExceededMaximumRetries] = dataclasses.field(default_factory=list)


class Instagram(commands.Cog):
    URL_REGEX = r"https?://(www\.)?instagram\.com/(p|tv|reel)/([a-zA-Z0-9]*)"
    FILESIZE_MIN = 10 ** 3
    FILESIZE_MAX = 8 * 10 ** 6  # 8 MB
    MAX_RETRIES = 3
    POST_CACHE_ENTRIES = 64

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(cookie_jar=OneTimeCookieJar())

        self.cookies_file = self.bot.config["cogs"]["instagram"]["cookies_file"]
        with open(self.cookies_file, "r") as f:
            cookies = json.load(f)

        self.session.cookie_jar.update_cookies(cookies=cookies)
        self.post_extractor = InstagramExtractorV2()
        self.post_cache = LeastRecentlyUsed(self.POST_CACHE_ENTRIES)

        logger.info(f"Loaded {len(self.session.cookie_jar)} cookies")

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    async def get_post(self, message: discord.Message, url: str):
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0",
        }

        params = {"__a": 1}

        async with ReactingRetryingSession(
            self.MAX_RETRIES,
            self.session.get,
            url,
            message=message,
            emoji=self.bot.custom_emoji["RETRY"],
            params=params,
            headers=headers,
        ) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                raise InstagramLoginException

        return self.post_extractor.extract_media(data)

    async def get_post_and_media(
        self, message: discord.Message, url: str
    ) -> IGPostResult:
        if cached := self.post_cache.get(url):
            return cached

        try:
            media = await self.get_post(message, url)
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
            await owner.send(f"Instagram broke! Msg: {message.jump_url}")
            raise commands.BadArgument(
                "Instagram broke :poop: Bot owner has been notified."
            )
        except ExceededMaximumRetries as e:
            raise commands.BadArgument(
                f"Failed fetching the Instagram post at `{e.url}` multiple ({e.tries}) times. Please try again later."
            )

        ig_post_result = IGPostResult()

        async def get_media(url: str) -> typing.Union[FileStub, str]:
            async with ReactingRetryingSession(
                self.MAX_RETRIES,
                self.session.get,
                yarl.URL(url, encoded=True),
                message=message,
                emoji=self.bot.custom_emoji["RETRY"],
            ) as response:
                filename = basename(urlparse(url).path)
                bytes = await response.read()
                filesize = BytesIO(bytes).getbuffer().nbytes

                if self.FILESIZE_MIN < filesize < self.FILESIZE_MAX:
                    return FileStub(filename, bytes)
                else:
                    return url

        results = await asyncio.gather(
            *[get_media(url) for url in media], return_exceptions=True
        )

        dont_cache = False

        for result in results:
            if type(result) == str:
                ig_post_result.urls.append(result)
                dont_cache = True
            elif type(result) == FileStub:
                ig_post_result.files.append(result)
            elif type(result) == ExceededMaximumRetries:
                ig_post_result.exceptions.append(result)
                dont_cache = True

        if not dont_cache:
            self.post_cache[url] = ig_post_result

        return ig_post_result

    @log_usage(command_name="ig_show")
    async def show_media(self, ctx, url):
        ig_post_result = await self.get_post_and_media(ctx.message, url)

        # remove discord's default instagram embed
        try:
            await ctx.message.edit(suppress=True)
        except discord.Forbidden:
            pass

        url_chunks = chunker(ig_post_result.urls, 5)
        for chunk in url_chunks:
            await ctx.send("\n".join(chunk))

        for file_stub in ig_post_result.files:
            filename, bytes_ = file_stub
            await ctx.send(files=[File(BytesIO(bytes_), filename=filename)])

        if len(ig_post_result.exceptions) > 0:
            await ctx.send(
                "Could not fetch the following files:\n"
                + "\n".join([str(exc.url) for exc in ig_post_result.exceptions])
            )

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

        async with (await self.bot.channel_locker.get(ctx)):
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
        if (
            ctx.valid
            or not ctx.guild
            or message.webhook_id
            or ctx.author == self.bot.user
        ):
            return

        results = regex.finditer(self.URL_REGEX, message.content)
        urls = [result.group(0) for result in results]

        if len(urls) > 0:
            confirm = await SimpleConfirm(
                message, emoji=UNICODE_EMOJI["INSPECT"]
            ).prompt(ctx)
            if confirm:
                async with (await self.bot.channel_locker.get(message.channel)):
                    async with ctx.typing():
                        for url in urls:
                            try:
                                await self.show_media(ctx, url)
                            except commands.BadArgument as error:
                                await ctx.send(error)

    async def cog_before_invoke(self, ctx):
        await ctx.trigger_typing()
