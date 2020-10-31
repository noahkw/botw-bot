import logging

import discord
from discord.ext import commands

from util import auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Greeters(bot))


def format_template(template, member: discord.Member):
    try:
        return template.format(
            mention=member.mention,
            id=member.id,
            number=member.guild.member_count,
            name=member.name,
            discriminator=member.discriminator,
            guild=member.guild.name,
        )
    except KeyError as e:
        raise commands.BadArgument(f"The placeholder `{e}` is not supported.")


class Greeters(commands.Cog):
    GREETER_NOT_SET = "{greeter} greeter has not been configured for this server."
    GREETER_DOESNT_EXIST = "This type of greeter does not exist."
    GREETERS = {"join": "join_greeter", "leave": "leave_greeter"}

    def __init__(self, bot):
        self.bot = bot

    async def _add_greeter(self, ctx, channel, template, greeter_type):
        query = """SELECT *
                   FROM greeters
                   WHERE guild = $1 AND type = $2;"""
        row = await self.bot.pool.fetchrow(query, ctx.guild.id, greeter_type)

        if channel and template:
            # test the template string. will raise if a wrong placeholder is used
            format_template(template, ctx.author)

            query = """INSERT INTO greeters (channel, guild, template, type)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (guild, type) DO UPDATE
                       SET channel = $1, template = $3;"""
            await self.bot.pool.execute(
                query, channel.id, ctx.guild.id, template, greeter_type
            )

            await ctx.send(
                f"{greeter_type} greeter set to `{template}` in {channel.mention}."
            )
        elif row and row["template"]:
            greeter_channel = self.bot.get_channel(row["channel"])
            await ctx.send(
                f'{greeter_type} greeter in {greeter_channel.mention}: `{row["template"]}`.'
            )
        else:
            raise commands.BadArgument(
                self.GREETER_NOT_SET.format(greeter=greeter_type)
            )

    @auto_help
    @commands.group(
        aliases=["greeter"],
        invoke_without_command=True,
        brief="Configure greeters for the server",
    )
    @commands.has_permissions(administrator=True)
    async def greeters(self, ctx):
        await ctx.send_help(self.greeters)

    @greeters.command(brief="Adds or displays the join greeter")
    @commands.has_permissions(administrator=True)
    async def join(self, ctx, channel: discord.TextChannel = None, *, template=None):
        """
        Adds a new greeter for when a user joins the server.
        Displays the current greeter if no arguments are specified.

        Example usage:
        `{prefix}greeters join #general Welcome {{mention}} to {{guild}}!`

        Available placeholders for the message:
        `{{mention}}`: Mentions the user
        `{{name}}`: The user's name
        `{{discriminator}}`: The user's discriminator
        `{{id}}`: The user's id
        `{{number}}`: The number of members in the server
        `{{guild}}`: The server's name
        """
        await self._add_greeter(ctx, channel, template, "join")

    @greeters.command(brief="Adds or displays the leave greeter")
    @commands.has_permissions(administrator=True)
    async def leave(self, ctx, channel: discord.TextChannel = None, *, template=None):
        """
        Adds a new greeter for when a user leaves the server.
        Displays the current greeter if no arguments are specified.

        Example usage:
        `{prefix}greeters leave #general {{name}} left {{guild}}!`

        Available placeholders for the message:
        `{{mention}}`: Mentions the user (not recommended here)
        `{{name}}`: The user's name
        `{{discriminator}}`: The user's discriminator
        `{{id}}`: The user's id
        `{{number}}`: The number of members in the server
        `{{guild}}`: The server's name
        """
        await self._add_greeter(ctx, channel, template, "leave")

    async def send_greeter(self, greeter, member):
        query = """SELECT channel, template FROM greeters
                   WHERE guild = $1 and type = $2;"""
        row = await self.bot.pool.fetchrow(query, member.guild.id, greeter)
        if not row:
            raise commands.BadArgument(self.GREETER_NOT_SET.format(greeter=greeter))

        channel = self.bot.get_channel(row["channel"])
        template = row["template"]
        if not channel or not template:
            raise commands.BadArgument(self.GREETER_NOT_SET.format(greeter=greeter))

        await channel.send(format_template(template, member))

    @greeters.command(brief="Tests the given greeter")
    @commands.has_permissions(administrator=True)
    async def test(self, ctx, greeter):
        """
        Tests the given greeter.

        Example usage:
        `{prefix}greeter test join`
        """
        greeter = greeter.lower()
        if greeter in self.GREETERS:
            await self.send_greeter(greeter, ctx.author)
        else:
            raise commands.BadArgument(self.GREETER_DOESNT_EXIST)

    @greeters.command(brief="Disables the given greeter in the given channel")
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx, greeter):
        """
        Disables the given greeter in the given channel.

        Example usage:
        `{prefix}greeter disable leave`
        """
        greeter = greeter.lower()
        if greeter in self.GREETERS:
            query = """DELETE FROM greeters
                       WHERE guild = $1 and type = $2
                       RETURNING channel, template;"""
            row = await self.bot.pool.fetchrow(query, ctx.guild.id, greeter)
            if not row:
                raise commands.BadArgument(self.GREETER_NOT_SET.format(greeter=greeter))

            old_channel = self.bot.get_channel(row["channel"])
            old_template = row["template"]

            await ctx.send(
                f"The {greeter} greeter in {old_channel.mention} was reset. Old message: `{old_template}`."
            )
        else:
            raise commands.BadArgument(self.GREETER_DOESNT_EXIST)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            await self.send_greeter("join", member)
        except commands.BadArgument:
            # we are not interested in join greeter not configured exceptions
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        try:
            await self.send_greeter("leave", member)
        except commands.BadArgument:
            # we are not interested in leave greeter not configured exceptions
            pass
