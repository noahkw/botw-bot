import logging
import random
import typing

import discord
from discord import Embed
from discord.ext import commands
from discord.utils import find

from const import SHOUT_EMOJI
from util import ack, git_version_label, git_short_history

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Utilities(bot))


class Utilities(commands.Cog):
    MOCK_HISTORY_LOOKBACK = 10

    def __init__(self, bot):
        self.bot = bot
        self.bot.version = git_version_label()
        self.shout_emoji = find(lambda e: e.name == SHOUT_EMOJI, self.bot.emojis)
        self.server_invite = "https://discord.gg/3ACGRke"

    @commands.command(brief="Displays the bot's ping")
    async def ping(self, ctx):
        await ctx.send(f".pong: Discord WebSocket: `{self.bot.latency * 1000:0.2f}` ms")

    @commands.command(brief="Reloads the bot's modules")
    @commands.is_owner()
    @ack
    async def reload(self, ctx):
        for ext in self.bot.config["enabled_cogs"]:
            self.bot.reload_extension(ext)

    @commands.command(aliases=["pick"], brief="Makes the bot choose between 2+ things")
    async def choose(self, ctx, *args: commands.clean_content):
        if len(args) < 2:
            await ctx.send("I want at least two things to choose from!")
        else:
            await ctx.send(f"I choose: `{random.choice(args)}`")

    @commands.command(aliases=["v"], brief="Displays the bot's version")
    async def version(self, ctx):
        await ctx.send(f"Running version `{self.bot.version}`.")

    @commands.command(brief="Repeats something in uppercase")
    async def shout(self, ctx, *, msg: commands.clean_content):
        await ctx.send(f"{self.shout_emoji} {msg.upper()}!")

    @commands.command(brief="Shows some info about the bot")
    async def info(self, ctx):
        embed = Embed(description=f"**Testing server**\n{self.server_invite}\n")
        # f'**Latest changes**\n{git_short_history()}') \
        embed.set_author(
            name=f"{self.bot.user.name} Info", icon_url=self.bot.user.avatar_url
        ).set_footer(
            text=f"Made by {self.bot.get_user(self.bot.CREATOR_ID)}. Running {self.bot.version}."
        ).set_thumbnail(
            url=self.bot.user.avatar_url_as(static_format="png")
        )

        servers = len(ctx.bot.guilds)
        members = sum(len(g.members) for g in ctx.bot.guilds)
        users = len(ctx.bot.users)
        members_online = sum(
            1
            for g in ctx.bot.guilds
            for m in g.members
            if m.status != discord.Status.offline
        )
        text_channels = sum(len(g.text_channels) for g in ctx.bot.guilds)
        voice_channels = sum(len(g.voice_channels) for g in ctx.bot.guilds)

        embed.add_field(
            name="Members",
            value=f"{members} total\n{users} unique\n{members_online} online",
        )
        embed.add_field(
            name="Channels", value=f"{text_channels} text\n{voice_channels} voice"
        )
        embed.add_field(name="Servers", value=servers)

        await ctx.send(embed=embed)

    @commands.command(brief="Shows the latest commits")
    @commands.is_owner()
    async def changelog(self, ctx, n=5):
        embed = Embed(description=git_short_history(n)).set_author(
            name=f"{self.bot.user.name} Changelog", icon_url=self.bot.user.avatar_url
        )

        await ctx.send(embed=embed)

    @commands.command(brief="Sends a message to a channel")
    @commands.has_permissions(administrator=True)
    @ack
    async def say(
        self, ctx, channel: typing.Optional[discord.TextChannel] = None, *, content
    ):
        if not channel:
            channel = ctx.channel

        try:
            await channel.send(
                content,
                allowed_mentions=discord.AllowedMentions(
                    everyone=True, users=True, roles=True
                ),
            )
        except discord.Forbidden:
            await ctx.send(f"I don't have permission to send messages in {channel}.")

    @commands.command(brief="Edits a message sent by the bot")
    @commands.has_permissions(administrator=True)
    @ack
    async def edit(self, ctx, message: discord.Message, *, content):
        if not message.guild == ctx.guild:
            await ctx.send("Can't edit messages in other servers.")

        try:
            await message.edit(
                content=content,
                allowed_mentions=discord.AllowedMentions(
                    everyone=True, users=True, roles=True
                ),
            )
        except discord.Forbidden:
            await ctx.send("Couldn't edit the message. It's probably ancient.")

    @commands.command(brief="Sends the guild's member count")
    async def members(self, ctx):
        await ctx.send(f"Member count: `{ctx.guild.member_count}`.")
