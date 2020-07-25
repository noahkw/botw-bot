import asyncio
import logging

import discord
from discord.ext import commands

from cogs import AinitMixin, CustomCog
from const import CHECK_EMOJI
from models import Profile
from util import ack

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Profiles(bot))


class Profiles(CustomCog, AinitMixin):
    def __init__(self, bot):
        super().__init__(bot)
        self.profiles = {}
        self.profiles_collection = self.bot.config['profiles']['profiles_collection']

        super(AinitMixin).__init__()

    async def _ainit(self):
        _profiles = await self.bot.db.get(self.profiles_collection)

        for profile in _profiles:
            user = self.bot.get_user(int(profile.id))
            self.profiles[user.id] = Profile.from_dict(user, profile.to_dict())

        logger.info(f'# Initial profiles from db: {len(self.profiles)}')

    async def _create_profile(self, user: discord.User):
        profile = Profile(user)
        self.profiles[user.id] = profile
        await self.bot.db.set(self.profiles_collection, str(user.id), profile.to_dict())

    async def get_profile(self, user: discord.User):
        await self.wait_until_ready()
        if user.id not in self.profiles:
            await self._create_profile(user)

        return self.profiles[user.id]

    async def set(self, user: discord.User, key, value):
        profile = await self.get_profile(user)
        attr = getattr(profile, key)
        attr.value = value
        await self.bot.db.update(self.profiles_collection, str(user.id), {key: value})

    @commands.group(invoke_without_command=True, brief='View or edit profiles')
    async def profile(self, ctx, user: discord.User = None):
        lookup = ctx.author if user is None else user
        profile = await self.get_profile(lookup)
        await ctx.send(embed=profile.to_embed())

    @profile.command(name='location')
    @ack
    async def location(self, ctx, *, location: commands.clean_content):
        await self.set(ctx.author, 'location', location)
