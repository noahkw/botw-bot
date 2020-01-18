import logging

from discord.ext import commands

logger = logging.getLogger(__name__)

def setup(bot):
    bot.add_cog(Utilities(bot))


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        await ctx.send(f'.pong: Discord WebSocket: `{self.bot.latency * 1000:0.2f}` ms')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reload(self, ctx):
        self.bot.reload_extension('cogs.BiasOfTheWeek')
        self.bot.reload_extension('cogs.Utilities')
        self.bot.reload_extension('cogs.Scheduler')
        self.bot.reload_extension('cogs.EmojiUtils')
        self.bot.reload_extension('cogs.Tags')

    @reload.error
    async def reload_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingPermissions):
            await ctx.send(error)
        logger.error(error)
