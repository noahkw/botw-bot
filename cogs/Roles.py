import logging
import typing

import asyncpg
import discord
from discord.ext import commands

from util import ack

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Roles(bot))


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
            else:
                await member.remove_roles(role, reason='Self-unassigned by member')
                await ctx.send(f'{member.mention}, you no longer have the role {role.mention}.')
        except discord.Forbidden:
            raise commands.BadArgument('I am not allowed to manage roles.')

    @commands.group(aliases=['r', 'role'], invoke_without_command=True)
    async def roles(self, ctx, role_alias=None):
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
        await ctx.send(f'Available roles in the server: {",".join(roles)}')

    @roles.command()
    @commands.has_permissions(administrator=True)
    async def create(self, ctx, role: discord.Role, clear_after: typing.Optional[int], *aliases):
        try:
            async with self.bot.pool.acquire() as connection:
                async with connection.transaction():
                    query_role = """INSERT INTO roles (guild, role, clear_after, active)
                                    VALUES ($1, $2, $3, TRUE);"""
                    await self.bot.pool.execute(query_role, ctx.guild.id, role.id, clear_after if clear_after else -1)
                    for alias in aliases + (role.name,):
                        query_alias = """INSERT INTO role_aliases (role, guild, alias)
                                         VALUES ($1, $2, $3);"""
                        await self.bot.pool.execute(query_alias, role.id, ctx.guild.id, alias)
        except asyncpg.exceptions.UniqueViolationError:
            raise commands.BadArgument(f'Either the role {role.mention} is already self-assignable '
                                       f'or one of the aliases is already used by another role.')

        await ctx.send(f'{role.mention} is now self-assignable.')

    # @create.error
    # async def create_error(self, ctx, error):
    #     logger.exception(error)

    @roles.command(aliases=['remove'])
    @commands.has_permissions(administrator=True)
    @ack
    async def delete(self, ctx, role: discord.Role):
        query = """DELETE FROM roles
                   WHERE role = $1;"""
        await self.bot.pool.execute(query, role.id)
