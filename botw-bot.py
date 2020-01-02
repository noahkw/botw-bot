import configparser
import logging

from discord.ext import commands
from BiasOfTheWeek import BiasOfTheWeek

config = configparser.ConfigParser()
config.read('conf.ini')
client = commands.Bot(command_prefix=config['discord']['command_prefix'])
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='botw-bot.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


@client.event
async def on_ready():
    print(f'Logged in as {client.user}')


client.add_cog(BiasOfTheWeek(client, config['biasoftheweek']))
client.run(config['discord']['token'])
