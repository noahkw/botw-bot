import asyncio
import logging

import aiohttp
from discord.ext import commands

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(UrlShortener(bot))


class BitlyException(Exception):
    pass


class BearerAuth(aiohttp.BasicAuth):
    def __init__(self, token):
        self.token = token

    def encode(self):
        return "Bearer " + self.token


class UrlShortener(commands.Cog):
    SHORTEN_ENDPOINT = 'https://api-ssl.bitly.com/v4/shorten'

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.auth = BearerAuth(self.bot.config['bitly']['access_token'])
        self.domain = self.bot.config['bitly']['domain']

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    async def shorten_url(self, url):
        payload = {
            'domain': self.domain,
            'long_url': url
        }

        async with self.session.post(self.SHORTEN_ENDPOINT, json=payload, auth=self.auth) as response:
            if 200 <= response.status < 300:
                data = await response.json()
                return data['link']
            else:
                data = await response.json()
                raise BitlyException(data['description'] if 'description' in data else data)

    @commands.group(invoke_without_command=True, brief='Shorten urls')
    async def url(self, ctx):
        await ctx.send_help(self.url)

    @url.command(aliases=['s'], brief='Shortens given URL(s)')
    @commands.cooldown(1, per=60, type=commands.BucketType.user)
    async def shorten(self, ctx, *urls):
        if len(urls) == 0:
            raise commands.BadArgument('Need at least one URL to shorten.')

        shortened_urls = []
        for url in urls:
            try:
                shortened_urls.append(await self.shorten_url(url))
            except BitlyException:
                await ctx.send(f'Could not shorten `{url}`. Make sure that it is a valid URL.')

        if len(shortened_urls) > 0:
            await ctx.send(f'Your shortened URL(s):')
            await ctx.send('```' + '\n'.join(shortened_urls) + '```')
