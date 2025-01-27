import logging

import discord
from discord.ext import commands

import db
from models import Greeter, GreeterType
from util import auto_help, GreeterTypeConverter, format_template

logger = logging.getLogger(__name__)


async def setup(bot):
    await bot.add_cog(Greeters(bot))


class Greeters(commands.Cog):
    GREETER_NOT_SET = "{greeter} greeter has not been configured for this server."

    def __init__(self, bot):
        self.bot = bot

        Greeter.inject_bot(bot)

    async def _add_greeter(
        self,
        session,
        ctx,
        channel: discord.TextChannel,
        template,
        greeter_type: GreeterType,
    ):
        if channel and template:
            # test the template string. will raise if a wrong placeholder is used
            format_template(template, ctx.author)

            greeter = Greeter(
                _guild=ctx.guild.id,
                _channel=channel.id,
                template=template,
                type=greeter_type,
            )
            await session.merge(greeter)

            await ctx.send(
                f"{greeter_type} greeter set to `{template}` in {channel.mention}."
            )
        elif (
            current_greeter := await db.get_greeter(session, ctx.guild.id, greeter_type)
        ) and current_greeter.template:
            await ctx.send(
                f"{greeter_type} greeter in {current_greeter.channel.mention}: `{current_greeter.template}`."
            )
        else:
            raise commands.BadArgument(
                self.GREETER_NOT_SET.format(greeter=greeter_type)
            )

    @auto_help
    @commands.group(
        aliases=["greeter"],
        brief="Configure greeters for the server",
    )
    @commands.has_permissions(administrator=True)
    async def greeters(self, ctx):
        if not ctx.invoked_subcommand:
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
        `{{id}}`: The user's id
        `{{number}}`: The number of members in the server
        `{{guild}}`: The server's name
        """
        async with self.bot.Session() as session:
            await self._add_greeter(session, ctx, channel, template, GreeterType.JOIN)
            await session.commit()

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
        `{{id}}`: The user's id
        `{{number}}`: The number of members in the server
        `{{guild}}`: The server's name
        """
        async with self.bot.Session() as session:
            await self._add_greeter(session, ctx, channel, template, GreeterType.LEAVE)
            await session.commit()

    async def send_greeter(
        self, session, greeter_type: GreeterType, member: discord.Member
    ):
        greeter = await db.get_greeter(session, member.guild.id, greeter_type)

        if not greeter:
            raise commands.BadArgument(
                self.GREETER_NOT_SET.format(greeter=greeter_type)
            )

        if not greeter.channel or not greeter.template:
            raise commands.BadArgument(
                self.GREETER_NOT_SET.format(greeter=greeter_type)
            )

        await greeter.channel.send(format_template(greeter.template, member))

    @greeters.command(brief="Tests the given greeter")
    @commands.has_permissions(administrator=True)
    async def test(self, ctx, greeter_type: GreeterTypeConverter):
        """
        Tests the given greeter.

        Example usage:
        `{prefix}greeter test join`
        """
        async with self.bot.Session() as session:
            await self.send_greeter(session, greeter_type, ctx.author)

    @greeters.command(brief="Disables the given greeter in the given channel")
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx, greeter_type: GreeterTypeConverter):
        """
        Disables the given greeter in the given channel.

        Example usage:
        `{prefix}greeter disable leave`
        """
        async with self.bot.Session() as session:
            try:
                channel_id, template = await db.delete_greeter(
                    session, ctx.guild.id, greeter_type
                )
            except TypeError:
                raise commands.BadArgument(
                    self.GREETER_NOT_SET.format(greeter=greeter_type)
                )

            await ctx.send(
                f"The {greeter_type} greeter in {self.bot.get_channel(channel_id).mention} "
                f"was reset. Old message: `{template}`."
            )

            await session.commit()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        async with self.bot.Session() as session:
            try:
                await self.send_greeter(session, GreeterType.JOIN, member)
            except commands.BadArgument:
                # we are not interested in join greeter not configured exceptions
                pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        async with self.bot.Session() as session:
            try:
                await self.send_greeter(session, GreeterType.LEAVE, member)
            except commands.BadArgument:
                # we are not interested in join greeter not configured exceptions
                pass
