import asyncio
import logging

import discord
from discord import Embed, Color
from discord.ext import tasks, commands

import db
from cogs import AinitMixin, CustomCog
from models import CustomRole, CustomRoleSettings, BlockedUser
from views import RoleCreatorView, RoleCreatorResult, CustomRoleSetup, CustomRoleDisable

logger = logging.getLogger(__name__)


class MissingRole(commands.CheckFailure):
    def __init__(self):
        super().__init__("You are missing a role to do this.")


def has_guild_role():
    async def predicate(ctx: commands.Context):
        async with ctx.bot.Session() as session:
            custom_role_settings = await db.get_custom_role_settings(
                session, ctx.guild.id
            )
            if ctx.author.guild_permissions.administrator or (
                custom_role_settings is not None
                and custom_role_settings._role in [role.id for role in ctx.author.roles]
            ):
                return True
            else:
                raise MissingRole

    return commands.check(predicate)


async def setup(bot):
    await bot.add_cog(CustomRoles(bot))


class CustomRoles(CustomCog, AinitMixin):
    def __init__(self, bot):
        super().__init__(bot)

        CustomRole.inject_bot(bot)
        CustomRoleSettings.inject_bot(bot)

        self._role_removal_loop.start()

    def cog_unload(self):
        self._role_removal_loop.stop()

    @commands.group(
        name="customroles", aliases=["customrole", "cr"], brief="Custom roles"
    )
    async def custom_roles(self, ctx: commands.Context):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.custom_roles)

    @custom_roles.command(brief="Set up custom roles")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx: commands.Context):
        embed = Embed(
            title="Set up custom roles",
            description="Choose the role below that members need to have in order to be allowed to create"
            " custom roles in the server, then hit confirm.",
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)

        await ctx.reply(view=CustomRoleSetup(), embed=embed, ephemeral=True)

    @custom_roles.command(brief="Disable custom roles")
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx: commands.Context):
        await ctx.reply(
            "Do you really want to disable custom roles in the server?"
            " All custom roles currently assigned to members will be deleted.",
            view=CustomRoleDisable(member=ctx.author),
            ephemeral=True,
        )

    @custom_roles.command(brief="Removes your custom role")
    @has_guild_role()
    async def delete(self, ctx: commands.Context):
        async with self.bot.Session() as session:
            custom_role = await db.get_user_custom_role_in_guild(
                session, ctx.author.id, ctx.guild.id
            )

            if custom_role is None:
                raise commands.BadArgument("You do not currently have a custom role.")

            if custom_role.role:
                role_name = custom_role.role.name
                await custom_role.role.delete(
                    reason=f"Custom role for {ctx.author} ({ctx.author.id}) removed manually"
                )
                await ctx.reply(f"Your role '{role_name}' has been deleted.")
            else:
                await ctx.reply("Your role has been deleted.")

            await db.delete_custom_role(session, ctx.guild.id, ctx.author.id)
            await session.commit()

    @custom_roles.command(brief="Creates a custom role for you")
    @has_guild_role()
    async def create(self, ctx: commands.Context):
        embed = Embed(
            title="Create custom role",
            description="Click below to create your own role.",
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)

        async def creation_callback(result: RoleCreatorResult):
            async with self.bot.Session() as session:
                member = ctx.guild.get_member(result.user_id)
                if member is None:
                    return

                custom_role_settings = await db.get_custom_role_settings(
                    session, ctx.guild.id
                )
                if custom_role_settings is None:
                    logger.info(
                        "creation callback in %s (%d) triggered but custom roles not set up",
                        str(ctx.guild),
                        ctx.guild.id,
                    )
                    return

                try:
                    role = await ctx.guild.create_role(
                        reason=f"Custom role for {member} ({result.user_id})",
                        name=result.name,
                        color=Color.from_str("#" + result.color),
                    )
                    await ctx.guild.edit_role_positions(
                        {role: custom_role_settings.role.position},
                        reason=f"Moving new custom role above {custom_role_settings.role}",
                    )
                    await member.add_roles(role, reason="Custom role added")

                    custom_role = CustomRole(
                        _role=role.id, _guild=ctx.guild.id, _user=result.user_id
                    )
                    session.add(custom_role)
                    await session.commit()
                except discord.Forbidden:
                    logger.info(
                        "no permissions to create custom roles in %s (%d)",
                        ctx.guild,
                        ctx.guild.id,
                    )
                    return

        view = RoleCreatorView(creation_callback, None)
        await ctx.send(view=view, embed=embed)

    @commands.Cog.listener()
    async def on_user_blocked(self, blocked_user: BlockedUser):
        async with self.bot.Session() as session:
            custom_role = await db.get_user_custom_role_in_guild(
                session, blocked_user._user, blocked_user._guild
            )

            if custom_role is None:
                return

            await self.delete_custom_role(session, custom_role)
            await session.commit()

    async def delete_custom_role(self, session, custom_role: CustomRole) -> None:
        try:
            logger.info(
                "removing custom role from %s (%d) in %s (%d)",
                str(custom_role.member),
                custom_role._user,
                str(custom_role.guild),
                custom_role._guild,
            )
            if custom_role.role is not None:
                await custom_role.role.delete(
                    reason=f"Member {custom_role.member} ({custom_role._user}) no longer has required role"
                    f" or was blocked, removing custom role"
                )
            await db.delete_custom_role(session, custom_role._guild, custom_role._user)
        except discord.Forbidden:
            logger.info(
                "no permissions to delete custom role in %s (%d) for user %s (%d)",
                str(custom_role.guild),
                custom_role._guild,
                str(custom_role.member),
                custom_role._user,
            )

    @tasks.loop(hours=24)
    async def _role_removal_loop(self) -> None:
        logger.info("running role removal task")
        async with self.bot.Session() as session:
            custom_roles = await db.get_custom_roles(session)

            role_deletion_tasks = []

            for custom_role in custom_roles:
                # TODO fix this N+1 issue
                custom_role_settings = await db.get_custom_role_settings(
                    session, custom_role._guild
                )

                member_has_guild_role = (
                    custom_role.member is not None
                    and custom_role_settings._role
                    in (member_role.id for member_role in custom_role.member.roles)
                )

                if not member_has_guild_role and (
                    custom_role.member is None
                    or not custom_role.member.guild_permissions.administrator
                ):
                    # member no longer has the guild's required role, add to deletion list
                    role_deletion_tasks.append(
                        self.delete_custom_role(session, custom_role)
                    )

            await asyncio.gather(*role_deletion_tasks)
            await session.commit()

    @_role_removal_loop.before_loop
    async def loop_before(self):
        await self.bot.wait_until_ready()
