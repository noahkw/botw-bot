import configparser
import logging
import cogs

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
    print(f'Logged in as {client.user}')


@client.event
async def on_disconnect():
    prtint('disconnected')


@client.check
async def globally_block_dms(ctx):
    return ctx.guild is not None


client.load_extension('cogs.BiasOfTheWeek')
client.load_extension('cogs.Utilities')
client.load_extension('cogs.Scheduler')
client.run(config['discord']['token'])
