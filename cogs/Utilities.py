import logging

from discord.ext import commands

logger = logging.getLogger('discord')

def setup(bot):
    bot.add_cog(Utilities(bot))


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reload(self, ctx):
        self.bot.reload_extension('cogs.BiasOfTheWeek')
        self.bot.reload_extension('cogs.Utilities')
        self.bot.reload_extension('cogs.Scheduler')
        self.bot.reload_extension('cogs.EmojiUtils')

    @reload.error
    async def reload_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingPermissions):
            await ctx.send(error)
        logger.error(error)
