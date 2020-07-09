import asyncio
import logging

import discord
from discord.ext import commands

from models import GuildSettings
from util import ack

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
            guild = self.bot.get_guild(int(setting.id))
            self.settings[guild] = GuildSettings.from_dict(guild, setting.to_dict())

        logger.info(f'# Initial settings from db: {len(self.settings)}')

    async def _create_settings(self, guild: discord.Guild):
        settings = GuildSettings(guild)
        self.settings[guild] = settings
        await self.bot.db.set(self.settings_collection, str(guild.id), settings.to_dict())

    async def get_settings(self, guild: discord.Guild):
        if guild not in self.settings:
            await self._create_settings(guild)

        return self.settings[guild]

    async def set(self, guild: discord.Guild, key, value):
        settings = await self.get_settings(guild)
        attr = getattr(settings, key)
        attr.value = value
        await self.bot.db.update(self.settings_collection, str(guild.id), {key: value})

    async def set_botw_state(self, guild, value):
        settings = await self.get_settings(guild)
        settings.botw_state.value = value
        await self.bot.db.update(self.settings_collection, str(guild.id), {'botw_state': value.name})

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        settings = await self.get_settings(ctx.guild)
        await ctx.send(embed=settings.to_embed())

    @settings.command(name='emojichannel')
    @commands.has_permissions(administrator=True)
    @ack
    async def set_emoji_channel(self, ctx, channel: discord.TextChannel):
        settings = await self.get_settings(ctx.guild)
        settings.emoji_channel.value = channel
        await self.bot.db.update(self.settings_collection, str(ctx.guild.id), {'emoji_channel': channel.id})

    @settings.command(name='prefix')
    @commands.has_permissions(administrator=True)
    @ack
    async def set_prefix(self, ctx, prefix):
        settings = await self.get_settings(ctx.guild)
        settings.prefix.value = prefix
        await self.bot.db.update(self.settings_collection, str(ctx.guild.id), {'prefix': prefix})
