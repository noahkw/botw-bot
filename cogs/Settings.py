import asyncio
import logging

import discord
from discord.ext import commands

from models import Profile, GuildSettings
from const import CHECK_EMOJI

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Settings(bot))


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = {}
        self.settings_collection = self.bot.config['settings']['settings_collection']

        if self.bot.loop.is_running():
            asyncio.create_task(self._ainit())
        else:
            self.bot.loop.run_until_complete(self._ainit())

    async def _ainit(self):
        _settings = await self.bot.db.get(self.settings_collection)

        for setting in _settings:
            self.settings[self.bot.get_guild(int(setting.id))] = GuildSettings.from_dict(setting.to_dict())

        logger.info(f'# Initial settings from db: {len(self.settings)}')

    async def _create_settings(self, guild: discord.Guild):
        settings = GuildSettings()
        self.settings[guild] = settings
        await self.bot.db.set(self.settings_collection, str(guild.id), settings.to_dict())

    async def get_settings(self, guild: discord.Guild):
        if guild not in self.settings:
            await self._create_settings(guild)

        return self.settings[guild]

    async def set(self, guild: discord.Guild, key, value):
        settings = await self.get_settings(guild)
        setattr(settings, key, value)
        await self.bot.db.update(self.settings_collection, str(guild.id), {key: value})

    async def set_botw_state(self, guild, value):
        settings = await self.get_settings(guild)
        settings.botw_state = value
        await self.bot.db.update(self.settings_collection, str(guild.id), {'botw_state': value.name})
