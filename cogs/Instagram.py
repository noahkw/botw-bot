import asyncio
import json
import logging
from io import BytesIO
from os.path import basename
from urllib.parse import urlparse

import aiohttp
from discord import File
from discord.ext import commands
from regex import regex

from const import INSPECT_EMOJI
from menu import SimpleConfirm
from util import chunker, auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Instagram(bot))


class Instagram(commands.Cog):
    URL_REGEX = r"https?://www.instagram.com/(p|tv)/(.*?)/"

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

        self.cookies_file = self.bot.config['instagram']['cookies_file']
        with open(self.cookies_file, 'r') as f:
            self.session.cookie_jar.update_cookies(cookies=json.load(f))

        logger.info(f'Loaded {len(self.session.cookie_jar)} cookies')

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    async def get_media(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0",
        }

        params = {
            '__a': 1
        }

        async with self.session.get(url, params=params, headers=headers) as response:
            data = await response.json()
            data = data['graphql']['shortcode_media']

        media_type = data['__typename']

        if media_type == 'GraphImage':
            return [data['display_url']]
        elif media_type == 'GraphVideo':
            return [data['video_url']]
        else:
            media = data['edge_sidecar_to_children']['edges']
            return [media['node']['display_url'] if
                    media['node']['__typename'] == 'GraphImage' else media['node']['video_url'] for media in media]

    async def show_media(self, ctx, url):
        media = await self.get_media(url)
        if len(media) == 0:
            raise commands.BadArgument('This Instagram post contains no images or videos.')

        files = []

        for url in media:
            async with self.session.get(url) as response:
                filename = basename(urlparse(url).path)
                file = File(BytesIO(await response.read()), filename=filename)
                files.append(file)

        # remove discord's default instagram embed
        await ctx.message.edit(suppress=True)

        chunks = chunker(files, 10)
        for chunk in chunks:
            await ctx.send(files=chunk)

    @auto_help
    @commands.group(aliases=['ig'], invoke_without_command=True, brief='Display posts from Instagram')
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
            raise commands.BadArgument('Invalid Instagram URL.')

        await self.show_media(ctx, url)

    @instagram.command()
    @commands.is_owner()
    async def reload(self, ctx):
        with open(self.cookies_file, 'r') as f:
            self.session.cookie_jar.update_cookies(cookies=json.load(f))

        await ctx.send(f'Loaded {len(self.session.cookie_jar)} cookies')

    @commands.Cog.listener('on_message')
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)
        if ctx.valid or not ctx.guild:
            return

        results = regex.finditer(self.URL_REGEX, message.content)
        urls = [result.group(0) for result in results]

        if len(urls) > 0:
            confirm = await SimpleConfirm(message, emoji=INSPECT_EMOJI).prompt(ctx)
            if confirm:
                async with ctx.typing():
                    for url in urls:
                        await self.show_media(ctx, url)

    async def cog_before_invoke(self, ctx):
        await ctx.trigger_typing()
