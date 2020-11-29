import logging
import typing

import asyncpg
import discord
import pendulum
from aioscheduler import TimedScheduler
from discord.ext import commands

import db
from cogs import CustomCog, AinitMixin
from models import RoleClear, RoleAlias, AssignableRole
from util import ack

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Roles(bot))


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

            for role_clear in role_clears:
                if role_clear.is_due():
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

    async def _clear_role(
        self, guild: discord.Guild, member: discord.Member, role: discord.Role
    ):
        async with self.bot.Session() as session:
            if guild:
                if member and role:
                    await member.remove_roles(role, reason="Automatic unassign")
                    logger.info(
                        f"Automatically unassigned {role} from {member} in {guild}."
                    )

            await db.delete_role_clear(session, member.id, role.id)

            await session.commit()

    async def _toggle_role(self, ctx, alias, member: discord.Member):
        async with self.bot.Session() as session:
            assignable_role = await db.get_role_by_alias(session, ctx.guild.id, alias)
            if not assignable_role:
                raise commands.BadArgument("This role does not exist.")

            role = assignable_role.role

            try:
                if role not in member.roles:
                    await member.add_roles(role, reason="Self-assigned by member")
                    await ctx.send(
                        f"{member.mention}, you now have the role {role.mention}."
                    )

                    if assignable_role.clear_after:
                        when = pendulum.now("UTC").add(
                            hours=assignable_role.clear_after
                        )

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

                        await session.commit()
                else:
                    await member.remove_roles(role, reason="Self-unassigned by member")
                    await ctx.send(
                        f"{member.mention}, you no longer have the role {role.mention}."
                    )
            except discord.Forbidden:
                raise commands.BadArgument("I am not allowed to manage roles.")

    @commands.group(aliases=["r", "role"], invoke_without_command=True)
    async def roles(self, ctx, *, role_alias=None):
        if role_alias:
            await self._toggle_role(ctx, role_alias, ctx.author)
        else:
            await ctx.send(f"Assign a role using `{ctx.prefix}role name`.")
            await ctx.invoke(self.list)

    @roles.command()
    async def list(self, ctx):
        async with self.bot.Session() as session:
            assignable_roles = await db.get_roles(session, ctx.guild.id)
            assignable_roles.sort(key=lambda a_role: a_role.role.position, reverse=True)

            roles = [a_role.role.mention for a_role in assignable_roles]

            if len(roles) > 0:
                await ctx.send(f'Available roles: {", ".join(roles)}')
            else:
                await ctx.send(
                    f"Try to make some roles self-assignable using `{ctx.prefix}role create`."
                )

    @roles.command()
    @commands.has_permissions(administrator=True)
    async def create(
        self, ctx, role: discord.Role, clear_after: typing.Optional[int], *aliases
    ):
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

            role_aliases = [
                RoleAlias(_role=role.id, _guild=ctx.guild.id, alias=alias)
                for alias in aliases
            ]

            for role_alias in role_aliases:
                try:
                    session.add(role_alias)
                except asyncpg.exceptions.UniqueViolationError:
                    raise commands.BadArgument(
                        f"The alias `{role_alias.alias}` is already in use."
                    )

            await session.commit()

            await ctx.send(f"{role.mention} is now self-assignable.")

    @roles.command(aliases=["remove"])
    @commands.has_permissions(administrator=True)
    @ack
    async def delete(self, ctx, role: discord.Role):
        async with self.bot.Session() as session:
            await db.delete_role(session, role.id)

    @roles.command()
    async def info(self, ctx, *, alias):
        async with self.bot.Session() as session:
            assignable_role = await db.get_role_by_alias(session, ctx.guild.id, alias)
            if not assignable_role:
                raise commands.BadArgument("This role does not exist.")

            aliases = [
                f"`{role_alias.alias}`" for role_alias in assignable_role.aliases
            ]
            await ctx.send(
                f'Role: {assignable_role.role.mention}, clears after: {assignable_role.clear_after or "∞"} hours.'
                f'\nAliases: {", ".join(aliases)}'
            )
