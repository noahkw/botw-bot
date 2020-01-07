from discord.ext import commands


def setup(bot):
    bot.add_cog(Utilities(bot))


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reload(self, ctx):
        self.bot.reload_extension('BiasOfTheWeek')
        self.bot.reload_extension('Utilities')
        self.bot.reload_extension('Scheduler')

    @reload.error
    async def reload_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingPermissions):
            await ctx.send(error)
        print(error)
