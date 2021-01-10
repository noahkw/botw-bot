import logging

import discord
from discord.ext import commands

from menu import Confirm
from models import GuildSettings
from util import safe_send, safe_mention

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Main(bot))


class Main(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.oauth_url = self.bot.config["discord"]["oauth_url"]

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

    @commands.command(brief="Request the bot for your guild")
    async def invite(self, ctx, guild_id: int):
        await self.bot.get_user(self.bot.CREATOR_ID).send(
            f"Request to whitelist guild `{guild_id}` from {ctx.author.mention} (`{ctx.author.id}`)."
        )

        await ctx.send(
            f"{ctx.author.mention}, I've relayed your request to get me added to the guild with "
            f"ID `{guild_id}`.\n"
        )

    @commands.command(brief="Adds a guild to the whitelist")
    @commands.is_owner()
    async def whitelist(self, ctx, guild_id: int, requester_id: int):
        guild = self.bot.get_guild(guild_id)
        requester = self.bot.get_user(requester_id)

        confirm = await Confirm(f"Whitelist `{guild}` ({guild_id})?").prompt(ctx)
        if not confirm:
            return

        async with self.bot.Session() as session:
            guild_settings = GuildSettings(_guild=guild_id, whitelisted=True)
            await session.merge(guild_settings)
            self.bot.whitelist.add(guild_id)

            await session.commit()

        message = await safe_send(
            requester,
            f"Hey, you may now invite me using the following URL:\n"
            f"<{self.oauth_url}>",
        )

        if not message:
            await ctx.send(
                f"Not allowed to DM {safe_mention(requester)} (`{requester_id}`)."
            )

        await ctx.send(f"Whitelisted `{guild}` (`{guild_id}`)!")

    @commands.command(brief="Removes a guild from the whitelist")
    @commands.is_owner()
    async def unwhitelist(self, ctx, guild_id: int):
        guild = self.bot.get_guild(guild_id)

        confirm = await Confirm(f"Un-whitelist `{guild}` ({guild_id})?").prompt(ctx)
        if not confirm:
            return

        async with self.bot.Session() as session:
            guild_settings = GuildSettings(_guild=guild_id, whitelisted=False)
            await session.merge(guild_settings)
            self.bot.whitelist.remove(guild_id)

            await session.commit()

        await guild.leave()
        await ctx.send(f"Un-whitelisted `{guild}` and left it!")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        whitelisted = guild.id in self.bot.whitelist or guild.owner == self.bot.user

        await self.bot.get_user(self.bot.CREATOR_ID).send(
            f"I was added to a {'whitelisted' if whitelisted else 'non-whitelisted'} "
            f"guild: {guild} (`{guild.id}`)\n"
            f"Owner: {guild.owner.mention} (`{guild.owner_id}`)"
        )

        if not whitelisted:
            await guild.leave()
