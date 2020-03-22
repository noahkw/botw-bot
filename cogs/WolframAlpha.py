import logging
import aiohttp

from discord.ext import commands

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(WolframAlpha(bot))


class WolframAlpha(commands.Cog):
    API_URL = 'https://api.wolframalpha.com/v1/result'

    def __init__(self, bot):
        self.bot = bot
        self.app_id = self.bot.config['wolframalpha']['app_id']

    @commands.command(name='wolframalpha', aliases=['wa'])
    async def wolfram_alpha(self, ctx, *, query):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    f'{WolframAlpha.API_URL}?appid={self.app_id}&i={query}'
            ) as response:
                if response.status != 200:
                    await ctx.send('The request to WolframAlpha\'s API failed.'
                                   )
                else:
                    content = await response.text()
                    if content is not None:
                        await ctx.send(content)
                    else:
                        await ctx.send(
                            'Try a different query. WolframAlpha is not cooperating.'
                        )
