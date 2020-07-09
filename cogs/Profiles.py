import asyncio
import logging

import discord
from discord.ext import commands

from const import CHECK_EMOJI
from models import Profile
from util import ack

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Profiles(bot))


class Profiles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.profiles = {}
        self.profiles_collection = self.bot.config['profiles']['profiles_collection']

        if self.bot.loop.is_running():
            asyncio.create_task(self._ainit())
        else:
            self.bot.loop.run_until_complete(self._ainit())

    async def _ainit(self):
        _profiles = await self.bot.db.get(self.profiles_collection)

        for profile in _profiles:
            user = self.bot.get_user(int(profile.id))
            self.profiles[user] = Profile.from_dict(user, profile.to_dict())

        logger.info(f'# Initial profiles from db: {len(self.profiles)}')

    async def _create_profile(self, user: discord.User):
        profile = Profile(user)
        self.profiles[user] = profile
        await self.bot.db.set(self.profiles_collection, str(user.id), profile.to_dict())

    async def get_profile(self, user: discord.User):
        if user not in self.profiles:
            await self._create_profile(user)

        return self.profiles[user]

    async def set(self, user: discord.User, key, value):
        profile = await self.get_profile(user)
        attr = getattr(profile, key)
        attr.value = value
        await self.bot.db.update(self.profiles_collection, str(user.id), {key: value})

    @commands.group(invoke_without_command=True)
    async def profile(self, ctx, user: discord.User = None):
        lookup = ctx.author if user is None else user
        profile = await self.get_profile(lookup)
        await ctx.send(embed=profile.to_embed())

    @profile.command(name='location')
    @ack
    async def location(self, ctx, *, location: commands.clean_content):
        await self.set(ctx.author, 'location', location)
