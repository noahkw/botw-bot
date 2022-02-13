import asyncio
import logging
import typing

import discord
import pendulum
from aioscheduler import TimedScheduler
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession

import db
from cogs import CustomCog, AinitMixin
from models import RoleClear, RoleAlias, AssignableRole
from util import ack

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Roles(bot))


class RoleOrAlias(commands.Converter):
    def __init__(self):
        self.role_converter = commands.RoleConverter()

    async def convert(self, ctx, argument):
        async with ctx.bot.Session() as session:
            try:
                role = await self.role_converter.convert(ctx, argument)
                assignable_role = await db.get_role(session, role.id)
            except commands.BadArgument:
                assignable_role = await db.get_role_by_alias(
                    session, ctx.guild.id, argument
                )

            if not assignable_role:
                raise commands.BadArgument("This role does not exist.")

            return assignable_role


class Roles(CustomCog, AinitMixin):
    def __init__(self, bot):
        super().__init__(bot)
        self.scheduler = TimedScheduler(prefer_utc=True)
        self.scheduler.start()

        AssignableRole.inject_bot(bot)
        RoleAlias.inject_bot(bot)
        RoleClear.inject_bot(bot)

    async def _ainit(self):
        await self.bot.wait_until_ready()

        async with self.bot.Session() as session:
            role_clears = await db.get_role_clears(session)

        async def scheduled_clear(role_clear: RoleClear):
            if not role_clear.guild:
                await db.delete_role_clear(
                    session, role_clear._member, role_clear._role
                )
            elif role_clear.is_due():
                await self._clear_role(
                    role_clear.guild, role_clear.member, role_clear.role
                )
            else:
                self.scheduler.schedule(
                    self._clear_role(
                        role_clear.guild, role_clear.member, role_clear.role
                    ),
                    role_clear.when,
                )

        await asyncio.gather(
            *[scheduled_clear(role_clear) for role_clear in role_clears]
        )

    async def _clear_role(
        self, guild: discord.Guild, member: discord.Member, role: discord.Role
    ) -> None:
        # Needs its own session as we schedule it for execution at a later time
        async with self.bot.Session() as session:
            try:
                await member.remove_roles(role, reason="Automatic unassign")
                logger.info(f"Automatically unassigned {role} from {member} in {guild}")
            except discord.DiscordException:
                pass

            await db.delete_role_clear(session, member.id, role.id)
            await session.commit()

    async def _toggle_role(
        self,
        session: AsyncSession,
        ctx: commands.Context,
        assignable_role: AssignableRole,
        member: discord.Member,
    ) -> None:
        role = assignable_role.role

        try:
            if role not in member.roles:
                await member.add_roles(role, reason="Self-assigned by member")
                await ctx.reply(
                    f"You now have the role {role.mention}.", mention_author=False
                )

                if assignable_role.clear_after:
                    when = pendulum.now("UTC").add(hours=assignable_role.clear_after)

                    self.scheduler.schedule(
                        self._clear_role(member.guild, member, role), when
                    )

                    role_clear = RoleClear(
                        _role=role.id,
                        _member=member.id,
                        _guild=ctx.guild.id,
                        when=when,
                    )
                    await session.merge(role_clear)
            else:
                await member.remove_roles(role, reason="Self-unassigned by member")
                await ctx.reply(
                    f"You no longer have the role {role.mention}.", mention_author=False
                )
        except discord.Forbidden:
            raise commands.BadArgument("I am not allowed to manage roles.")

    async def _list_roles(self, session: AsyncSession, ctx: commands.Context):
        assignable_roles = await db.get_roles(session, ctx.guild.id)
        roles_to_show = []

        for a_role in assignable_roles:
            if not a_role.role:
                await session.delete(a_role)
                await ctx.send(
                    f"Removing assignable role that no longer exists: `{a_role.aliases[0].alias}`"
                )
            else:
                roles_to_show.append(a_role)

        roles_to_show.sort(key=lambda a_role: a_role.role.position, reverse=True)
        roles = [a_role.role.mention for a_role in roles_to_show]

        if len(roles) > 0:
            await ctx.send(f'Available roles: {", ".join(roles)}')
        else:
            await ctx.send(
                f"Try to make some roles self-assignable using `{ctx.prefix}role create`."
            )

    @commands.group(aliases=["r", "role"], invoke_without_command=True)
    async def roles(
        self, ctx: commands.Context, *, role: typing.Optional[RoleOrAlias]
    ) -> None:
        async with self.bot.Session() as session:
            if role:
                await self._toggle_role(session, ctx, role, ctx.author)
            else:
                await ctx.send(f"Assign a role using `{ctx.prefix}role name`.")
                await self._list_roles(session, ctx)

            await session.commit()

    @roles.command(name="list", brief="Lists all assignable roles in the server")
    async def list_roles(self, ctx: commands.Context) -> None:
        async with self.bot.Session() as session:
            await self._list_roles(session, ctx)
            await session.commit()

    @roles.command(brief="Creates a new assignable role")
    @commands.has_permissions(administrator=True)
    async def create(
        self,
        ctx: commands.Context,
        role: discord.Role,
        clear_after: typing.Optional[int],
        *aliases: str,
    ) -> None:
        async with self.bot.Session() as session:
            if await db.get_role(session, role.id):
                raise commands.BadArgument(
                    f"{role.mention} is already self-assignable."
                )

            assignable_role = AssignableRole(
                _guild=ctx.guild.id, _role=role.id, clear_after=clear_after
            )
            session.add(assignable_role)

            aliases = set(aliases + (role.name,))

            for alias in aliases:
                if await db.get_role_by_alias(session, ctx.guild.id, alias):
                    raise commands.BadArgument(
                        f"The alias `{alias}` is already in use."
                    )

                session.add(RoleAlias(_role=role.id, _guild=ctx.guild.id, alias=alias))

            await session.commit()

            await ctx.send(f"{role.mention} is now self-assignable.")

    @roles.command(aliases=["remove"], brief="Removes an assignable role")
    @commands.has_permissions(administrator=True)
    @ack
    async def delete(self, ctx: commands.Context, *, role: RoleOrAlias) -> None:
        async with self.bot.Session() as session:
            await db.delete_role(session, role.role.id)
            await session.commit()

    @roles.command(brief="Diplays info on an assignable role")
    async def info(self, ctx: commands.Context, *, role: RoleOrAlias):
        aliases = [f"`{role_alias.alias}`" for role_alias in role.aliases]
        await ctx.send(
            f'Role: {role.role.mention}, clears after: {role.clear_after or "∞"} hours.'
            f'\nAliases: {", ".join(aliases)}'
        )
