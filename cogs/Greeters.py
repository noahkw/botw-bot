import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Greeters(bot))


def format_template(template, member: discord.Member):
    try:
        return template.format(mention=member.mention, id=member.id, number=member.guild.member_count,
                               name=member.name, discriminator=member.discriminator, guild=member.guild.name)
    except KeyError as e:
        raise commands.BadArgument(f'The placeholder `{e}` is not supported.')


class Greeters(commands.Cog):
    GREETER_NOT_SET = '{greeter} greeter has not been configured for this server.'
    GREETER_DOESNT_EXIST = 'This type of greeter does not exist.'
    GREETERS = {'join': 'join_greeter', 'leave': 'leave_greeter'}

    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=['greeter'], invoke_without_command=True)
    async def greeters(self, ctx):
        await ctx.send_help(self.greeters)

    @greeters.command()
    @commands.has_permissions(administrator=True)
    async def join(self, ctx, channel: discord.TextChannel = None, *, template=None):
        """
        Add a new greeter for when a user joins the server.
        Displays the current greeter if no arguments are specified.

        Example usage:
            greeters join #general Welcome {mention} to {guild}!

        Available placeholders for the message:
        {mention}: Mentions the user
        {name}: The user's name
        {discriminator}: The user's discriminator
        {id}: The user's id
        {number}: The number of members in the server
        {guild}: The server's name
        """
        settings_cog = self.bot.get_cog('Settings')
        settings = await settings_cog.get_settings(ctx.guild)

        if channel and template:
            # test the template string. will raise if a wrong placeholder is used
            format_template(template, ctx.author)

            await settings_cog.update(ctx.guild, 'join_greeter', channel, template)
            await ctx.send(f'Join greeter set to `{template}` in {channel.mention}.')
        elif settings.join_greeter.template:
            await ctx.send(f'Join greeter in {settings.join_greeter.channel.mention}: `{settings.join_greeter.template}`.')
        else:
            raise commands.BadArgument(self.GREETER_NOT_SET.format(greeter='Join'))

    @greeters.command()
    @commands.has_permissions(administrator=True)
    async def leave(self, ctx, channel: discord.TextChannel = None, *, template=None):
        """
        Add a new greeter for when a user leaves the server.
        Displays the current greeter if no arguments are specified.

        Example usage:
            greeters leave #general {name} left {guild}!

        Available placeholders for the message:
        {mention}: Mentions the user (not recommended in leave greeter)
        {name}: The user's name
        {discriminator}: The user's discriminator
        {id}: The user's id
        {number}: The number of members in the server
        {guild}: The server's name
        """
        settings_cog = self.bot.get_cog('Settings')
        settings = await settings_cog.get_settings(ctx.guild)

        if channel and template:
            # test the template string. will raise if a wrong placeholder is used
            format_template(template, ctx.author)

            await settings_cog.update(ctx.guild, 'leave_greeter', channel, template)
            await ctx.send(f'Leave greeter set to `{template}` in {channel.mention}.')
        elif settings.leave_greeter.template:
            await ctx.send(
                f'Leave greeter in {settings.leave_greeter.channel.mention}: `{settings.leave_greeter.template}`.')
        else:
            raise commands.BadArgument(self.GREETER_NOT_SET.format(greeter='Leave'))

    async def send_greeter(self, greeter, member):
        settings_cog = self.bot.get_cog('Settings')
        settings = await settings_cog.get_settings(member.guild)

        channel, template = getattr(settings, self.GREETERS[greeter]).value
        if not channel or not template:
            raise commands.BadArgument(self.GREETER_NOT_SET.format(greeter=greeter))

        await channel.send(format_template(template, member))

    @greeters.command()
    @commands.has_permissions(administrator=True)
    async def test(self, ctx, greeter):
        """
        Test the given greeter.
        """
        greeter = greeter.lower()
        if greeter in self.GREETERS:
            await self.send_greeter(greeter, ctx.author)
        else:
            raise commands.BadArgument(self.GREETER_DOESNT_EXIST)

    @greeters.command()
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx, greeter, channel: discord.TextChannel):
        """
        Disables the given greeter in the given channel.
        """
        greeter = greeter.lower()
        if greeter in self.GREETERS:
            settings_cog = self.bot.get_cog('Settings')
            settings = await settings_cog.get_settings(ctx.guild)
            old_template = getattr(settings, self.GREETERS[greeter]).template

            await settings_cog.update(ctx.guild, self.GREETERS[greeter], None, None)
            await ctx.send(f'The {greeter} greeter in {channel.mention} was reset. Old message: `{old_template}`.')
        else:
            raise commands.BadArgument(self.GREETER_DOESNT_EXIST)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            await self.send_greeter('join', member)
        except commands.BadArgument:
            # we are not interested in join greeter not configured exceptions
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        try:
            await self.send_greeter('leave', member)
        except commands.BadArgument:
            # we are not interested in leave greeter not configured exceptions
            pass
