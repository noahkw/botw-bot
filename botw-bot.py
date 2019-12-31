import discord
import configparser

client = discord.Client()
config = configparser.ConfigParser()
config.read('conf.ini')


@client.event
async def on_ready():
    print(f'Logged in as {client.user}')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

client.run(config['discord']['token'])
