import logging
from collections import Counter

import discord
from discord.ext import commands


def cmd_to_str(group=False):
    newline = '\n' if group else ' '

    def actual(cmd):
        help = cmd.brief or cmd.help
        return f'**{cmd.name}**{newline}{help or "No description"}\n'

    return actual


class EmbedHelpCommand(commands.DefaultHelpCommand):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def embed(self, name=None):
        bot = self.context.bot
        heading = f' - {name}' if name else ''
        return discord.Embed(description=self.get_ending_note()) \
            .set_author(name=f'{bot.user.name} Help{heading}', icon_url=bot.user.avatar_url) \
            .set_footer(text=f'Made by {bot.get_user(bot.CREATOR_ID)}. Running {bot.version}.')

    def format_help(self, text):
        return text.format(prefix=self.clean_prefix)

    async def send_cog_help(self, cog):
        name = type(cog).__name__
        await self.send_group_help(cog.bot.get_command(name.lower()))

    async def send_command_help(self, command):
        embed = self.embed(name=command.qualified_name)
        embed.add_field(name='Usage', value=self.get_command_signature(command), inline=False)
        if help := (command.help or command.brief):
            embed.add_field(name='Description', value=self.format_help(help), inline=False)

        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        embed = self.embed(name=group.qualified_name)
        embed.add_field(name='Usage', value=self.get_command_signature(group), inline=False)
        if help := (group.help or group.brief):
            embed.add_field(name='Description', value=help, inline=False)

        filtered = await self.filter_commands(group.commands, sort=self.sort_commands)

        groups = [group for group in filtered if isinstance(group, commands.Group)]
        cmds = [cmd for cmd in filtered if not isinstance(cmd, commands.Group)]

        if len(groups) > 0:
            embed.add_field(name='Categories', value=' '.join(map(cmd_to_str(group=True), groups)), inline=False)

        embed.add_field(name='Subcommands', value=' '.join(map(cmd_to_str(), cmds)), inline=False)

        await self.get_destination().send(embed=embed)

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        filtered = await self.filter_commands(bot.commands, sort=self.sort_commands)

        groups = [group for group in filtered if isinstance(group, commands.Group)]
        top_level_commands = [cmd for cmd in filtered if not isinstance(cmd, commands.Group)]

        embed = self.embed() \
            .add_field(name='Categories', value=' '.join(map(cmd_to_str(group=True), groups)), inline=False) \
            .add_field(name='Various', value=' '.join(map(cmd_to_str(), top_level_commands)), inline=False)

        await self.get_destination().send(embed=embed)


class BotwBot(commands.Bot):
    CREATOR_ID = 207955387909931009

    INITIAL_EXTENSIONS = [
        'cogs.BiasOfTheWeek',
        'cogs.Utilities',
        'cogs.Instagram',
        'cogs.EmojiUtils',
        'cogs.Tags',
        'cogs.Trolling',
        'cogs.WolframAlpha',
        'cogs.Reminders',
        'cogs.Weather',
        'cogs.Profiles',
        'cogs.Mirroring',
        'cogs.Greeters',
        'cogs.Fun',
        'cogs.Gfycat',
        'jishaku'
    ]

    def __init__(self, config, **kwargs):
        self.config = config
        super().__init__(**kwargs, command_prefix=self.config['discord']['command_prefix'],
                         help_command=EmbedHelpCommand(),
                         allowed_mentions=discord.AllowedMentions(everyone=False, users=True, roles=False))
        self.add_checks()

        # ban after more than 5 commands in 10 seconds
        self.spam_cd = commands.CooldownMapping.from_cooldown(5, 10, commands.BucketType.user)
        self._spam_count = Counter()
        self.blacklist = set()

        self.prefixes = {}  # guild.id -> prefix

        def make_prefix_cmd():
            @commands.command(brief='Sets the prefix for the current guild')
            @commands.has_permissions(administrator=True)
            async def prefix(ctx, prefix=None):
                if not prefix:
                    await ctx.send(f'The current prefix is `{self.prefixes[ctx.guild.id]}`.')
                elif 1 <= len(prefix) <= 10:
                    query = """INSERT INTO prefixes (guild, prefix)
                                           VALUES ($1, $2)
                                           ON CONFLICT (guild) DO UPDATE
                                           SET prefix = $2;"""

                    await self.pool.execute(query, ctx.guild.id, prefix)
                    self.prefixes[ctx.guild.id] = prefix
                    await ctx.send(f'The prefix for this guild has been changed to `{prefix}`.')
                else:
                    raise commands.BadArgument('The prefix has to be between 1 and 10 characters long.')

            return prefix

        self.add_command(make_prefix_cmd())

    async def on_ready(self):
        await self.change_presence(activity=discord.Game('with Bini'))

        # cache the guild prefixes
        query = """SELECT *
                   FROM prefixes;"""

        rows = await self.pool.fetch(query)
        for row in rows:
            self.prefixes[row['guild']] = row['prefix']

        for ext in self.INITIAL_EXTENSIONS:
            ext_logger = logging.getLogger(ext)
            ext_logger.setLevel(logging.INFO)
            ext_logger.addHandler(handler)
            self.load_extension(ext)

        logger.info(f"Logged in as {self.user}. Whitelisted servers: {self.config.items('whitelisted_servers')}")

    async def on_disconnect(self):
        logger.info('disconnected')

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound) or hasattr(ctx.command, 'on_error'):
            return

        error = getattr(error, 'original', error)

        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument, commands.MissingPermissions,
                              commands.DisabledCommand)):
            await ctx.send(error)
            return

        logger.exception(error)

    def add_checks(self):
        async def globally_block_dms(ctx):
            return ctx.guild is not None or await self.is_owner(ctx.author)

        async def whitelisted_server(ctx):
            server_ids = [int(server) for key, server in ctx.bot.config.items('whitelisted_servers')]
            return ctx.guild is None or ctx.guild.id in server_ids

        self.add_check(globally_block_dms)
        self.add_check(whitelisted_server)

    def run(self):
        super().run(self.config['discord']['token'])

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

        if retry_after:
            await message.channel.send(
                f'{message.author.mention}, stop spamming and retry when this message is deleted!',
                delete_after=retry_after + 5)

            self._spam_count[message.author.id] += 1

            if self._spam_count[message.author.id] >= 5:
                self.blacklist.add(message.author.id)
                await message.channel.send(f'{message.author.mention}, you have been blacklisted from using commands!')

            return
        else:
            self._spam_count.pop(message.author.id, None)

        await super().process_commands(message)


logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='botw-bot.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)
