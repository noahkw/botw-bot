import configparser
import logging

import discord
from discord.ext import commands

from DataStore import FirebaseDataStore

config = configparser.ConfigParser()
config.read('conf.ini')
client = commands.Bot(command_prefix=config['discord']['command_prefix'])
client.config = config
client.database = FirebaseDataStore(
    config['firebase']['key_file'], config['firebase']['db_name'])
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(
    filename='botw-bot.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter(
    '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


@client.event
async def on_ready():
    await client.change_presence(activity=discord.Game('with Bini'))
    logger.info(f"Logged in as {client.user}. Whitelisted servers: {config.items('whitelisted_servers')}")

    client.load_extension('cogs.BiasOfTheWeek')
    client.load_extension('cogs.Utilities')
    client.load_extension('cogs.Scheduler')


@client.event
async def on_disconnect():
    logger.info('disconnected')


@client.check
async def globally_block_dms(ctx):
    return ctx.guild is not None


@client.check
async def whitelisted_server(ctx):
    server_ids = [int(server) for key, server in config.items('whitelisted_servers')]
    return ctx.guild.id in server_ids


client.run(config['discord']['token'])

logger.info('Cleaning up')
