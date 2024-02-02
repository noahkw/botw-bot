import logging
from functools import wraps

import discord
from discord import app_commands
from discord.ext import commands

import db
from botwbot import BotwBot
from menu import Confirm
from models import GuildSettings, GuildCog, BlockedUser
from util import safe_send, safe_mention, detail_mention, ack

logger = logging.getLogger(__name__)


async def setup(bot: BotwBot):
    await bot.add_cog(Main(bot), guilds=await bot.get_guilds_for_cog(Main))


def owner_only_autocomplete(coro):
    @wraps(coro)
    async def wrapped(interaction: discord.Interaction, *args, **kwargs):
        if interaction.user.id != interaction.client.CREATOR_ID:
            return [app_commands.Choice(name="Insufficient permissions", value="")]

        return await coro(interaction, *args, **kwargs)

    return wrapped


@owner_only_autocomplete
async def privileged_cog_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=cog_name, value=cog_name)
        for cog_name in BotwBot.PRIVILEGED_COGS
        if current.lower() in cog_name.lower()
    ]


@owner_only_autocomplete
async def guild_id_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=guild.name, value=str(guild.id))
        for guild in interaction.client.guilds
        if current.lower() in guild.name.lower()
    ]


class Main(commands.Cog):
    def __init__(self, bot):
        self.bot: BotwBot = bot
        self.oauth_url = self.bot.config["discord"]["oauth_url"]

    @commands.command(brief="Sets the prefix for the current guild")
    @commands.has_permissions(administrator=True)
    async def prefix(self, ctx: commands.Context, prefix=None):
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

    @commands.hybrid_command(brief="Request the bot for your guild")
    async def invite(self, ctx: commands.Context, guild_id: int):
        await self.bot.get_user(self.bot.CREATOR_ID).send(
            f"Request to whitelist guild `{guild_id}` from {detail_mention(ctx.author)}."
        )

        await ctx.reply(
            f"I've relayed your request to get me added to the guild with ID `{guild_id}`.\n"
        )

    @commands.hybrid_command(
        name="whitelistcog",
        brief="Whitelist a privileged cog for a guild",
        guild=661348382740054036,
    )
    @commands.is_owner()
    @app_commands.autocomplete(cog_name=privileged_cog_autocomplete)
    @app_commands.autocomplete(guild_id=guild_id_autocomplete)
    async def whitelist_cog(self, ctx: commands.Context, guild_id: str, cog_name: str):
        guild = ctx.bot.get_guild(int(guild_id))

        if guild is None:
            raise commands.BadArgument(
                f"Could not find guild with ID '{guild_id}' in cache."
            )
        elif cog_name not in BotwBot.PRIVILEGED_COGS:
            raise commands.BadArgument(f"'{cog_name}' is not a privileged cog.")

        async with ctx.bot.Session() as session:
            guild_cog = GuildCog(cog=cog_name, _guild=guild.id)
            await session.merge(guild_cog)

            await session.commit()

        ctx.bot.invalidate_privileged_cog_cache(cog_name)
        await ctx.reply(
            f"Successfully whitelisted cog '{cog_name}' for guild {guild_cog.guild}. "
            f"Consider reloading all cogs for the changes to apply."
        )

    @commands.command(brief="Adds a guild to the whitelist")
    @commands.is_owner()
    async def whitelist(self, ctx: commands.Context, guild_id: int, requester_id: int):
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
    async def unwhitelist(self, ctx: commands.Context, guild_id: int):
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
    async def activity(self, ctx: commands.Context, type_, *, message):
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

    @commands.command(brief="Block a user from using the bot")
    @commands.has_permissions(administrator=True)
    @ack
    async def block(self, ctx: commands.Context, member: discord.Member):
        if member is None:
            raise commands.BadArgument("Need a user.")

        async with self.bot.Session() as session:
            blocked_user = BlockedUser(_guild=ctx.guild.id, _user=member.id)
            await session.merge(blocked_user)
            await session.commit()

            self.bot.blocked_users.setdefault(ctx.guild.id, set()).add(member.id)
            self.bot.dispatch("user_blocked", blocked_user)

    @commands.command(brief="Unblock a user from using the bot")
    @commands.has_permissions(administrator=True)
    @ack
    async def unblock(self, ctx: commands.Context, member: discord.Member):
        if member is None:
            raise commands.BadArgument("Need a user.")

        async with self.bot.Session() as session:
            await db.delete_blocked_user(session, ctx.guild.id, member.id)
            await session.commit()

            blocked_users_in_guild = self.bot.blocked_users.get(ctx.guild.id)
            if blocked_users_in_guild is not None:
                blocked_users_in_guild.remove(member.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.bot.get_user(self.bot.CREATOR_ID).send(
            f"I was added to a guild: {detail_mention(guild)}\nOwner: {detail_mention(guild.owner)}"
        )

        await self.bot.whitelisted_or_leave(guild)
