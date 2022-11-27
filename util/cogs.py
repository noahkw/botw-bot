from discord.ext import commands


class PrivilegedCog(commands.Cog):
    async def check_privileged(self, ctx):
        guilds = await ctx.bot.get_guilds_for_cog(self)
        if ctx.guild is not None and ctx.guild not in guilds:
            raise PrivilegedCogNoPermissions(self.__cog_name__)

    async def cog_before_invoke(self, ctx):
        await self.check_privileged(ctx)


class PrivilegedCogNoPermissions(commands.CheckFailure):
    def __init__(self, cog_name):
        super().__init__(f"{cog_name} is not enabled in this server.")
