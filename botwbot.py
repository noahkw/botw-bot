import logging
from collections import Counter

import discord
from discord.ext import commands

import db


logger = logging.getLogger(__name__)


def cmd_to_str(group=False):
    newline = "\n" if group else " "

    def actual(cmd):
        help_ = cmd.brief or cmd.help
        return f'**{cmd.name}**{newline}{help_ or "No description"}\n'

    return actual


class EmbedHelpCommand(commands.DefaultHelpCommand):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def embed(self, name=None):
        bot = self.context.bot
        heading = f" - {name}" if name else ""
        return (
            discord.Embed(description=self.get_ending_note())
            .set_author(
                name=f"{bot.user.name} Help{heading}", icon_url=bot.user.avatar_url
            )
            .set_footer(
                text=f"Made by {bot.get_user(bot.CREATOR_ID)}. Running {bot.version}."
            )
        )

    def format_help(self, text):
        return text.format(prefix=self.clean_prefix)

    async def send_cog_help(self, cog):
        name = type(cog).__name__
        await self.send_group_help(cog.bot.get_command(name.lower()))

    async def send_command_help(self, command):
        embed = self.embed(name=command.qualified_name)
        embed.add_field(
            name="Usage", value=self.get_command_signature(command), inline=False
        )
        if help_ := (command.help or command.brief):
            embed.add_field(
                name="Description", value=self.format_help(help_), inline=False
            )

        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        embed = self.embed(name=group.qualified_name)
        embed.add_field(
            name="Usage", value=self.get_command_signature(group), inline=False
        )
        if help_ := (group.help or group.brief):
            embed.add_field(name="Description", value=help_, inline=False)

        filtered = await self.filter_commands(group.commands, sort=self.sort_commands)

        groups = [group for group in filtered if isinstance(group, commands.Group)]
        cmds = [cmd for cmd in filtered if not isinstance(cmd, commands.Group)]

        if len(groups) > 0:
            embed.add_field(
                name="Categories",
                value=" ".join(map(cmd_to_str(group=True), groups)),
                inline=False,
            )

        embed.add_field(
            name="Subcommands", value=" ".join(map(cmd_to_str(), cmds)), inline=False
        )

        await self.get_destination().send(embed=embed)

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        filtered = await self.filter_commands(bot.commands, sort=self.sort_commands)

        groups = [group for group in filtered if isinstance(group, commands.Group)]
        top_level_commands = [
            cmd for cmd in filtered if not isinstance(cmd, commands.Group)
        ]

        embed = (
            self.embed()
            .add_field(
                name="Categories",
                value=" ".join(map(cmd_to_str(group=True), groups)),
                inline=False,
            )
            .add_field(
                name="Various",
                value=" ".join(map(cmd_to_str(), top_level_commands)),
                inline=False,
            )
        )

        await self.get_destination().send(embed=embed)


class BotwBot(commands.Bot):
    CREATOR_ID = 207955387909931009

    def __init__(self, config, **kwargs):
        # the Session is attached by the launcher script
        self.Session = None
        self.config = config

        intents = discord.Intents.default()
        intents.members = True

        super().__init__(
            **kwargs,
            command_prefix=self.config["discord"]["command_prefix"],
            help_command=EmbedHelpCommand(),
            intents=intents,
            allowed_mentions=discord.AllowedMentions(
                everyone=False, users=True, roles=False
            ),
        )
        self.add_checks()

        # ban after more than 5 commands in 10 seconds
        self.spam_cd = commands.CooldownMapping.from_cooldown(
            5, 10, commands.BucketType.user
        )
        self._spam_count = Counter()
        self.blacklist = set()

        self.prefixes = {}  # guild.id -> prefix
        self.whitelist = set()  # guild.id

    async def on_ready(self):
        await self.change_presence(activity=discord.Game("with Bini"))

        if self.Session:
            async with self.Session() as session:
                # cache guild prefixes and whitelist
                settings = await db.get_guild_settings(session)
                for guild_settings in settings:
                    if prefix := guild_settings.prefix:
                        self.prefixes[guild_settings._guild] = prefix

                    if guild_settings.whitelisted:
                        self.whitelist.add(guild_settings._guild)

        for ext in self.config["enabled_cogs"]:
            self.load_extension(ext)

        logger.info(f"Logged in as {self.user}. Whitelisted servers: {self.whitelist}")

    async def on_disconnect(self):
        logger.info("disconnected")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound) or hasattr(
            ctx.command, "on_error"
        ):
            return

        error = getattr(error, "original", error)

        if isinstance(
            error,
            (
                commands.BadArgument,
                commands.MissingRequiredArgument,
                commands.MissingPermissions,
                commands.DisabledCommand,
                commands.CommandOnCooldown,
            ),
        ):
            await ctx.send(error)
            return

        logger.exception(error)

    def add_checks(self):
        async def globally_block_dms(ctx):
            return ctx.guild is not None or await self.is_owner(ctx.author)

        async def whitelisted_server(ctx):
            return (
                ctx.guild is None
                or self.Session is None
                or ctx.guild.id in self.whitelist
            )

        self.add_check(globally_block_dms)
        self.add_check(whitelisted_server)

    def run(self):
        super().run(self.config["discord"]["token"])

    async def get_prefix(self, message):
        if not message.guild:
            return self.command_prefix

        prefix = self.prefixes.setdefault(message.guild.id, self.command_prefix)

        return commands.when_mentioned_or(prefix)(self, message)

    async def process_commands(self, message):
        ctx = await self.get_context(message)

        if ctx.command is None or message.author.id in self.blacklist:
            return

        # spam control
        bucket = self.spam_cd.get_bucket(message)
        retry_after = bucket.update_rate_limit()

        if retry_after and message.author.id != self.owner_id:
            await message.channel.send(
                f"{message.author.mention}, stop spamming and retry when this message is deleted!",
                delete_after=retry_after + 5,
            )

            self._spam_count[message.author.id] += 1

            if self._spam_count[message.author.id] >= 5:
                self.blacklist.add(message.author.id)
                await message.channel.send(
                    f"{message.author.mention}, you have been blacklisted from using commands!"
                )

            return
        else:
            self._spam_count.pop(message.author.id, None)

        await super().process_commands(message)
