import logging

import discord
from discord.ext import commands

from cogs import AinitMixin, CustomCog
from models import GuildSettings
from util import ack, auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Settings(bot))


class Settings(CustomCog, AinitMixin):
    def __init__(self, bot):
        super().__init__(bot)
        self.settings = {}
        self.settings_collection = self.bot.config['settings']['settings_collection']

        super(AinitMixin).__init__()

    async def _ainit(self):
        _settings = await self.bot.db.get(self.settings_collection)

        await self.bot.wait_until_ready()

        for setting in _settings:
            guild = self.bot.get_guild(int(setting.id))
            self.settings[guild.id] = GuildSettings.from_dict(guild, setting.to_dict())

        logger.info(f'# Initial settings from db: {len(self.settings)}')

    async def _create_settings(self, guild: discord.Guild):
        logger.info(f'Creating guild settings for "{guild}"')
        settings = GuildSettings(guild)
        self.settings[guild.id] = settings
        await self.bot.db.set(self.settings_collection, str(guild.id), settings.to_dict())

    async def get_settings(self, guild: discord.Guild):
        await self.wait_until_ready()
        if guild.id not in self.settings:
            await self._create_settings(guild)

        return self.settings[guild.id]

    async def update(self, guild: discord.Guild, attr, *values):
        settings = await self.get_settings(guild)
        db_value = settings.update(attr, *values)
        await self.bot.db.update(self.settings_collection, str(guild.id), {attr: db_value})

    @auto_help
    @commands.group(invoke_without_command=True, brief='Change the bot\'s behavior in the server')
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        settings = await self.get_settings(ctx.guild)
        await ctx.send(embed=settings.to_embed())

    @settings.command(name='emojichannel')
    @commands.has_permissions(administrator=True)
    @ack
    async def set_emoji_channel(self, ctx, channel: discord.TextChannel):
        """
        Set the text channel where the bot keeps an up-to-date emoji list.
        """
        await self.update(ctx.guild, 'emoji_channel', channel)

    @settings.command(name='prefix')
    @commands.has_permissions(administrator=True)
    @ack
    async def set_prefix(self, ctx, prefix):
        """
        Set the command prefix for the bot.

        Default prefix: .
        Mentioning the bot is an alternative that always works. Example: @bot help
        """
        await self.update(ctx.guild, 'prefix', prefix)
