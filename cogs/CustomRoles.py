import asyncio
import logging

import discord
from discord import Embed, Color
from discord.ext import tasks, commands

import db
from cogs import AinitMixin, CustomCog

from models import CustomRole
from views import RoleCreatorView, RoleCreatorResult

logger = logging.getLogger(__name__)


class NotBoosting(commands.CheckFailure):
    def __init__(self):
        super().__init__("You are not a server booster.")


def is_booster():
    def predicate(ctx: commands.Context):
        if (
            ctx.author.premium_since is None
            and not ctx.author.guild_permissions.administrator
        ):
            raise NotBoosting

        return True

    return commands.check(predicate)


async def setup(bot):
    await bot.add_cog(CustomRoles(bot))


class CustomRoles(CustomCog, AinitMixin):
    def __init__(self, bot):
        super().__init__(bot)

        CustomRole.inject_bot(bot)

    @commands.group(aliases=["customrole", "cr"], brief="Custom roles")
    async def custom_roles(self, ctx: commands.Context):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.custom_roles)

    @custom_roles.command(brief="Removes your custom role")
    @is_booster()
    async def delete(self, ctx: commands.Context):
        async with self.bot.Session() as session:
            custom_role = await db.get_user_custom_role_in_guild(
                session, ctx.author.id, ctx.guild.id
            )

            if custom_role is None:
                raise commands.BadArgument("You do not currently have a custom role.")

            role_name = custom_role.role.name
            await custom_role.role.delete(
                reason=f"Custom role for {ctx.author} ({ctx.author.id}) removed manually"
            )
            await db.delete_custom_role(session, ctx.guild.id, ctx.author.id)

            await session.commit()
            await ctx.reply(f"Your role '{role_name}' has been deleted.")

    @custom_roles.command(brief="Creates a custom role for you")
    @is_booster()
    async def create(self, ctx: commands.Context):
        embed = Embed(
            title="Create custom role",
            description="Click below to create your own role.",
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)

        async def creation_callback(result: RoleCreatorResult):
            async with self.bot.Session() as session:
                member = ctx.guild.get_member(result.user_id)
                if not member:
                    return

                try:
                    role = await ctx.guild.create_role(
                        reason=f"Custom role for {member} ({result.user_id})",
                        name=result.name,
                        color=Color.from_str("#" + result.color),
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

    async def _delete_custom_role(self, session, custom_role: CustomRole) -> None:
        try:
            logger.info(
                "removing custom role from %s (%d) in %s (%d)",
                str(custom_role.guild),
                custom_role._guild,
                str(custom_role.member),
                custom_role._member,
            )
            await custom_role.role.delete(
                reason=f"Member {custom_role.member} ({custom_role.member.id}) removed their boost"
            )
            await db.delete_custom_role(session, custom_role._guild, custom_role._user)
        except discord.Forbidden:
            logger.info(
                "no permissions to delete custom role in %s (%d) for user %s (%d)",
                str(custom_role.guild),
                custom_role._guild,
                str(custom_role.member),
                custom_role._member,
            )

    @tasks.loop(hours=24.0)
    async def _role_removal_loop(self) -> None:
        logger.info("running role removal task")
        async with self.bot.Session() as session:
            custom_roles = await db.get_custom_roles(session)

            role_deletion_tasks = []

            for custom_role in custom_roles:
                if custom_role.member.premium_since is None:
                    # member is no longer boosting, add to deletion list
                    role_deletion_tasks.append(
                        self._delete_custom_role(session, custom_role)
                    )

            await asyncio.gather(*custom_roles)
