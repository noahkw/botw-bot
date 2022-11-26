import logging
import typing

import discord
from discord.ext import commands

from menu import Confirm
from models import GuildSettings
from util import safe_send, safe_mention, detail_mention, ack

logger = logging.getLogger(__name__)


async def setup(bot):
    await bot.add_cog(Main(bot))


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
    async def invite(self, ctx, guild_id: typing.Optional[int] = 0):
        # await self.bot.get_user(self.bot.CREATOR_ID).send(
        #    f"Request to whitelist guild `{guild_id}` from {detail_mention(ctx.author)}."
        # )

        # await ctx.send(
        #    f"{ctx.author.mention}, I've relayed your request to get me added to the guild with "
        #    f"ID `{guild_id}`.\n"
        # )
        await ctx.send("Invites are currently disabled.")

    @commands.command(brief="Adds a guild to the whitelist")
    @commands.is_owner()
    async def whitelist(self, ctx, guild_id: int, requester_id: int):
        requester = self.bot.get_user(requester_id)

        confirm = await Confirm(f"Whitelist guild `{guild_id}`?").prompt(ctx)
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

        await ctx.send(f"Whitelisted guild `{guild_id}`!")

    @commands.command(brief="Removes a guild from the whitelist")
    @commands.is_owner()
    async def unwhitelist(self, ctx, guild_id: int):
        guild = self.bot.get_guild(guild_id)

        confirm = await Confirm(
            f"Un-whitelist {detail_mention(guild, id=guild_id)}?"
        ).prompt(ctx)
        if not confirm:
            return

        async with self.bot.Session() as session:
            guild_settings = GuildSettings(_guild=guild_id, whitelisted=False)
            await session.merge(guild_settings)
            try:
                self.bot.whitelist.remove(guild_id)
            except KeyError:
                raise commands.BadArgument(
                    f"Guild {detail_mention(guild, id=guild_id)} is not whitelisted."
                )

            await session.commit()

        await ctx.send(f"Un-whitelisted {detail_mention(guild)} and left it!")

        try:
            await guild.leave()
        except (discord.Forbidden, AttributeError):
            logger.info("Could not leave guild %d after un-whitelisting", guild_id)

    @commands.command(brief="Sets the bot's activity")
    @commands.is_owner()
    @ack
    async def activity(self, ctx, type_, *, message):
        try:
            activity_type = discord.ActivityType[type_.lower()]
        except KeyError:
            raise commands.BadArgument(
                f"Activity type `{type_}` not supported. Try one of the following: `"
                f"{', '.join([e.name for e in discord.ActivityType])}`."
            )

        await self.bot.change_presence(
            activity=discord.Activity(type=activity_type, name=message)
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.bot.get_user(self.bot.CREATOR_ID).send(
            f"I was added to a guild: {detail_mention(guild)}\nOwner: {detail_mention(guild.owner)}"
        )

        await self.bot.whitelisted_or_leave(guild)
