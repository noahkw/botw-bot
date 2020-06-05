import configparser
import logging

import discord
from discord.ext import commands

from DataStore import FirebaseDataStore

config = configparser.ConfigParser()
config.read('conf.ini')
bot = commands.Bot(command_prefix=config['discord']['command_prefix'])
bot.config = config
bot.db = FirebaseDataStore(config['firebase']['key_file'], config['firebase']['db_name'], bot.loop)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='botw-bot.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

INITIAL_EXTENSIONS = [
    'cogs.BiasOfTheWeek', 'cogs.Utilities', 'cogs.Scheduler',
    'cogs.EmojiUtils', 'cogs.Tags', 'cogs.Trolling', 'cogs.WolframAlpha',
    'cogs.Reminders', 'cogs.Weather', 'jishaku'
]


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game('with Bini'))
    logger.info(f"Logged in as {bot.user}. Whitelisted servers: {config.items('whitelisted_servers')}")

    for ext in INITIAL_EXTENSIONS:
        ext_logger = logging.getLogger(ext)
        ext_logger.setLevel(logging.INFO)
        ext_logger.addHandler(handler)
        bot.load_extension(ext)


@bot.event
async def on_disconnect():
    logger.info('disconnected')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error


@bot.check
async def globally_block_dms(ctx):
    return ctx.guild is not None


@bot.check
async def whitelisted_server(ctx):
    server_ids = [int(server) for key, server in config.items('whitelisted_servers')]
    return ctx.guild.id in server_ids


bot.run(config['discord']['token'])

logger.info('Cleaning up')
