import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Greeters(bot))


def format_template(template, member: discord.Member):
    return template.format(mention=member.mention, id=member.id, number=member.guild.member_count,
                           name=member.name, discriminator=member.discriminator, guild=member.guild.name)


class Greeters(commands.Cog):
    GREETER_NOT_SET = '{greeter} greeter has not been configured for this server.'
    GREETER_DOESNT_EXIST = 'This type of greeter does not exist.'

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
            await settings_cog.update(ctx.guild, 'join_greeter', channel, template)
            await ctx.send(f'Join greeter set to `{template}` in {channel.mention}.')
        elif settings.join_greeter.template:
            await ctx.send(f'Join greeter in {settings.join_greeter.channel.mention}: `{settings.join_greeter.template}`.')
        else:
            raise commands.BadArgument(self.GREETER_NOT_SET.format(greeter='Join'))

    async def send_join_greeter(self, member):
        settings_cog = self.bot.get_cog('Settings')
        settings = await settings_cog.get_settings(member.guild)

        channel, template = settings.join_greeter.value
        if not channel or not template:
            raise commands.BadArgument(self.GREETER_NOT_SET.format(greeter='Join'))

        await channel.send(format_template(template, member))

    @greeters.command()
    @commands.has_permissions(administrator=True)
    async def test(self, ctx, greeter):
        """
        Test the given greeter.
        """
        if greeter.lower() == 'join':
            await self.send_join_greeter(ctx.author)
        else:
            raise commands.BadArgument(self.GREETER_DOESNT_EXIST)

    @greeters.command()
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx, greeter, channel: discord.TextChannel):
        """
        Disables the given greeter in the given channel.
        """
        if greeter.lower() == 'join':
            settings_cog = self.bot.get_cog('Settings')
            settings = await settings_cog.get_settings(ctx.guild)
            old_template = settings.join_greeter.template

            await settings_cog.update(ctx.guild, 'join_greeter', None, None)
            await ctx.send(f'The join greeter in {channel.mention} was reset. Old message: `{old_template}`.')
        else:
            raise commands.BadArgument(self.GREETER_DOESNT_EXIST)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            await self.send_join_greeter(member)
        except commands.BadArgument:
            # we are not interested in join greeter not configured exceptions
            pass
