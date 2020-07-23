import configparser
import logging
from collections import Counter

import discord
from discord.ext import commands

from DataStore import FirebaseDataStore


class BotwBot(commands.Bot):
    INITIAL_EXTENSIONS = [
        'cogs.BiasOfTheWeek', 'cogs.Utilities', 'cogs.Settings', 'cogs.Instagram',
        'cogs.EmojiUtils', 'cogs.Tags', 'cogs.Trolling', 'cogs.WolframAlpha',
        'cogs.Reminders', 'cogs.Weather', 'cogs.Profiles', 'cogs.Mirroring',
        'cogs.Greeters', 'jishaku',
    ]

    def __init__(self, config_path, **kwargs):
        self.startup = True
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        super().__init__(**kwargs, command_prefix=self.config['discord']['command_prefix'])
        self.db = FirebaseDataStore(self.config['firebase']['key_file'], self.config['firebase']['db_name'], self.loop)
        self.add_checks()

        # ban after more than 5 commands in 10 seconds
        self.spam_cd = commands.CooldownMapping.from_cooldown(5, 10, commands.BucketType.user)
        self._spam_count = Counter()
        self.blacklist = set()

    async def on_ready(self):
        await self.change_presence(activity=discord.Game('with Bini'))
        if self.startup:
            self.startup = False
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

        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument, commands.MissingPermissions)):
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

        settings_cog = self.get_cog('Settings')
        settings = await settings_cog.get_settings(message.guild)

        prefix = settings.prefix.value if settings.prefix.value is not None else self.command_prefix

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


if __name__ == '__main__':
    logger = logging.getLogger('discord')
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(filename='botw-bot.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

    botw_bot = BotwBot('conf.ini')
    botw_bot.run()

    logger.info('Cleaning up')
