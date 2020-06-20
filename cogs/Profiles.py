import asyncio
import logging

import discord
from discord.ext import commands

from models import Profile
from const import CHECK_EMOJI

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
            self.profiles[self.bot.get_user(int(profile.id))] = Profile.from_dict(profile.to_dict())

        logger.info(f'Initial profiles from db: {self.profiles}')

    async def _create_profile(self, member: discord.Member):
        profile = Profile()
        self.profiles[member] = profile
        await self.bot.db.set(self.profiles_collection, str(member.id), profile.to_dict())

    async def get_profile(self, member: discord.Member):
        if member not in self.profiles:
            await self._create_profile(member)

        return self.profiles[member]

    @commands.group(invoke_without_command=True)
    async def profile(self, ctx, member: discord.Member = None):
        lookup = ctx.author if member is None else member
        profile = await self.get_profile(lookup)
        await ctx.send(embed=profile.to_embed(lookup))

    @profile.command(name='location')
    async def location(self, ctx, *, location: commands.clean_content):
        profile = await self.get_profile(ctx.author)
        profile.location = location
        await self.bot.db.update(self.profiles_collection, str(ctx.author.id), {'location': location})
        await ctx.message.add_reaction(CHECK_EMOJI)
