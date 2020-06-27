import asyncio
import logging

import aiohttp
from discord.ext import commands
from regex import regex

from menu import Confirm
from util import chunker

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Instagram(bot))


class Instagram(commands.Cog):
    URL_REGEX = r"https?://www.instagram.com/(p|tv)/(.*?)/"

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    async def get_media(self, url):
        result = regex.match(self.URL_REGEX, url)
        if result:
            url = result.group(0)
        else:
            raise commands.BadArgument('Invalid Instagram URL.')

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

    @commands.group(aliases=['ig'], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def instagram(self, ctx, args=None):
        if args:
            await ctx.invoke(self.show, url=args)
        else:
            await ctx.send_help(self.instagram)

    @instagram.command()
    async def show(self, ctx, url):
        media = await self.get_media(url)
        if len(media) == 0:
            raise commands.BadArgument('This Instagram post contains no images or videos.')

        chunks = chunker(media, 4)
        for chunk in chunks:
            await ctx.send('\n'.join(chunk))

    @commands.Cog.listener('on_message')
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        result = regex.match(self.URL_REGEX, message.content)
        if result:
            url = result.group(0)
            confirm = await Confirm(f'Do you want me to embed this IG post?').prompt(ctx)
            if confirm:
                await ctx.invoke(self.show, url=url)
