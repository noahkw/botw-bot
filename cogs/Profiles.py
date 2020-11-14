import logging

import discord
from discord.ext import commands
from sqlalchemy.exc import NoResultFound

import db
from models import Profile
from util import auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Profiles(bot))


class Profiles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        Profile.inject_bot(bot)

    async def _create_profile(self, session, user: discord.User):
        """
        Creates a profile for given user. The caller has to guarantee that the
        user doesn't already have one.
        """
        profile = Profile(_user=user.id)
        session.add(profile)

        return profile

    async def get_profile(self, session, user: discord.User):
        try:
            profile = await db.get_profile(session, user.id)
        except NoResultFound:
            profile = await self._create_profile(session, user)

        return profile

    async def update(self, session, user: discord.User, item, new_value):
        if item not in Profile.EDITABLE:
            raise commands.BadArgument(f"Can't update {item}")

        profile = await self.get_profile(session, user)
        await profile.update(session, item, new_value)

    @auto_help
    @commands.group(invoke_without_command=True, brief="View or edit profiles")
    async def profile(self, ctx, user: discord.User = None):
        user = user or ctx.author
        async with self.bot.Session() as session:
            profile = await self.get_profile(session, user)
            await ctx.send(embed=profile.to_embed())

    @profile.command(name="location")
    async def location(self, ctx, *, location: commands.clean_content):
        async with self.bot.Session() as session:
            await self.update(session, ctx.author, "location", location)
            await session.commit()

            await ctx.send(f"Successfully set your location to `{location}`.")
