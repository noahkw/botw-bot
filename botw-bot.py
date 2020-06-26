import configparser
import logging
import asyncio

import discord
from discord.ext import commands

from DataStore import FirebaseDataStore


class BotwBot(commands.Bot):
    INITIAL_EXTENSIONS = [
        'cogs.BiasOfTheWeek', 'cogs.Utilities', 'cogs.Settings',
        'cogs.EmojiUtils', 'cogs.Tags', 'cogs.Trolling', 'cogs.WolframAlpha',
        'cogs.Reminders', 'cogs.Weather', 'cogs.Profiles', 'jishaku',
    ]

    def __init__(self, config_path, **kwargs):
        self.startup = True
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        super().__init__(**kwargs, command_prefix=self.config['discord']['command_prefix'])
        self.db = FirebaseDataStore(self.config['firebase']['key_file'], self.config['firebase']['db_name'], self.loop)
        self.add_checks()

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
            return ctx.guild is not None

        async def whitelisted_server(ctx):
            server_ids = [int(server) for key, server in ctx.bot.config.items('whitelisted_servers')]
            return ctx.guild is None or ctx.guild.id in server_ids

        self.add_check(globally_block_dms)
        self.add_check(whitelisted_server)

    def run(self):
        super().run(self.config['discord']['token'])


if __name__ == '__main__':
    logger = logging.getLogger('discord')
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(filename='botw-bot.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

    botw_bot = BotwBot('conf.ini')
    botw_bot.run()

    logger.info('Cleaning up')
