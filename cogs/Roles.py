import logging
import typing

import asyncpg
import discord
import pendulum
from aioscheduler import TimedScheduler
from discord.ext import commands

from cogs import CustomCog, AinitMixin
from util import ack, has_passed

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Roles(bot))


class Roles(CustomCog, AinitMixin):
    def __init__(self, bot):
        super().__init__(bot)
        self.scheduler = TimedScheduler(prefer_utc=True)
        self.scheduler.start()

    async def _ainit(self):
        await self.bot.wait_until_ready()

        query = """SELECT *
                   FROM role_clears;"""
        role_clears = await self.bot.pool.fetch(query)

        for role_clear in role_clears:
            if has_passed(role_clear['when']):
                await self._clear_role(role_clear['guild'], role_clear['member'], role_clear['role'])
            else:
                self.scheduler.schedule(self._clear_role(role_clear['guild'], role_clear['member'], role_clear['role']),
                                        role_clear['when'])

    async def _clear_role(self, guild: int, member: int, role: int):
        guild_ = self.bot.get_guild(guild)
        if guild_:
            member_ = guild_.get_member(member)
            role_ = guild_.get_role(role)

            if member_ and role_:
                await member_.remove_roles(role_, reason='Automatic unassign')
                logger.info(f'Automatically unassigned {role_} from {member_} in {guild_}.')

        query = """DELETE FROM role_clears
                   WHERE member = $1 AND role = $2;"""
        await self.bot.pool.execute(query, member, role)

    async def _toggle_role(self, ctx, alias, member: discord.Member):
        query_alias = """SELECT *
                         FROM role_aliases NATURAL JOIN roles
                         WHERE guild = $1 AND alias = $2 AND active = TRUE;"""
        row = await self.bot.pool.fetchrow(query_alias, member.guild.id, alias)
        if not row:
            raise commands.BadArgument(f'This role does not exist.')

        role = member.guild.get_role(row['role'])

        try:
            if role not in member.roles:
                await member.add_roles(role, reason='Self-assigned by member')
                await ctx.send(f'{member.mention}, you now have the role {role.mention}.')

                if clear_after := row['clear_after']:
                    when = pendulum.now('UTC').add(hours=clear_after)

                    self.scheduler.schedule(self._clear_role(member.guild.id, member.id, role.id), when)
                    query_schedule_clear = """INSERT INTO role_clears
                                              VALUES ($1, $2, $3, $4);"""
                    await self.bot.pool.execute(query_schedule_clear, role.id, member.id, when, member.guild.id)
            else:
                await member.remove_roles(role, reason='Self-unassigned by member')
                await ctx.send(f'{member.mention}, you no longer have the role {role.mention}.')
        except discord.Forbidden:
            raise commands.BadArgument('I am not allowed to manage roles.')

    @commands.group(aliases=['r', 'role'], invoke_without_command=True)
    async def roles(self, ctx, *, role_alias=None):
        if role_alias:
            await self._toggle_role(ctx, role_alias, ctx.author)
        else:
            await ctx.send(f'Assign a role using `{ctx.prefix}role name`.')
            await ctx.invoke(self.list)

    @roles.command()
    async def list(self, ctx):
        query = """SELECT *
                   FROM roles
                   WHERE guild = $1;"""

        rows = await self.bot.pool.fetch(query, ctx.guild.id)

        roles = [ctx.guild.get_role(row['role']).mention for row in rows]

        if len(roles) > 0:
            await ctx.send(f'Available roles: {", ".join(roles)}')
        else:
            await ctx.send(f'Try to make some roles self-assignable using `{ctx.prefix}role create`.')

    @roles.command()
    @commands.has_permissions(administrator=True)
    async def create(self, ctx, role: discord.Role, clear_after: typing.Optional[int], *aliases):
        async with self.bot.pool.acquire() as connection:
            async with connection.transaction():
                query_role = """INSERT INTO roles (guild, role, clear_after, active)
                                VALUES ($1, $2, $3, TRUE);"""
                try:
                    await connection.execute(query_role, ctx.guild.id, role.id, clear_after if clear_after else -1)
                except asyncpg.exceptions.UniqueViolationError:
                    raise commands.BadArgument(f'{role.mention} is already self-assignable.')

                aliases = set(aliases + (role.name,))
                for alias in aliases:
                    query_alias = """INSERT INTO role_aliases (role, guild, alias)
                                     VALUES ($1, $2, $3);"""
                    try:
                        await connection.execute(query_alias, role.id, ctx.guild.id, alias)
                    except asyncpg.exceptions.UniqueViolationError:
                        raise commands.BadArgument(f'The alias `{alias}` is already in use.')

        await ctx.send(f'{role.mention} is now self-assignable.')

    @roles.command(aliases=['remove'])
    @commands.has_permissions(administrator=True)
    @ack
    async def delete(self, ctx, role: discord.Role):
        query = """DELETE FROM roles
                   WHERE role = $1;"""
        await self.bot.pool.execute(query, role.id)

    @roles.command()
    async def info(self, ctx, *, alias):
        query_alias = """SELECT *
                         FROM role_aliases NATURAL JOIN roles
                         WHERE guild = $1 AND alias = $2 AND active = TRUE;"""
        row = await self.bot.pool.fetchrow(query_alias, ctx.guild.id, alias)
        if not row:
            raise commands.BadArgument(f'This role does not exist.')

        role = ctx.guild.get_role(row['role'])

        query_aliases = """SELECT *
                           FROM role_aliases
                           WHERE role = $1;"""
        rows = await self.bot.pool.fetch(query_aliases, role.id)

        aliases = [f"`{row['alias']}`" for row in rows]
        await ctx.send(f'Role: {role.mention}, clears after: {row["clear_after"]} hours.'
                       f'\nAliases: {", ".join(aliases)}')
