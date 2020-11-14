import logging

from discord.ext import commands

from menu import Confirm
from models import GuildSettings
from util import ack

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Main(bot))


class Main(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Sets the prefix for the current guild")
    @commands.has_permissions(administrator=True)
    async def prefix(self, ctx, prefix=None):
        if not prefix:
            await ctx.send(
                f"The current prefix is `{self.bot.prefixes[ctx.guild.id]}`."
            )
        elif 1 <= len(prefix) <= 10:
            async with ctx.bot.Session() as session:
                settings = GuildSettings(_guild=ctx.guild.id, prefix=prefix)
                await session.merge(settings)
                await session.commit()
                self.bot.prefixes[ctx.guild.id] = prefix
                await ctx.send(
                    f"The prefix for this guild has been changed to `{prefix}`."
                )
        else:
            raise commands.BadArgument(
                "The prefix has to be between 1 and 10 characters long."
            )

    @commands.command(brief="Adds a guild to the whitelist")
    @commands.is_owner()
    @ack
    async def whitelist(self, ctx, guild_id: int):
        guild = self.bot.get_guild(guild_id)

        confirm = await Confirm(f"Whitelist `{guild}` ({guild_id})?").prompt(ctx)
        if not confirm:
            return

        async with self.bot.Session() as session:
            guild_settings = GuildSettings(_guild=guild_id, whitelisted=True)
            await session.merge(guild_settings)
            self.bot.whitelist.add(guild_id)

            await session.commit()
