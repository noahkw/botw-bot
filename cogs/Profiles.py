import logging

import discord
from discord.ext import commands

from models import Profile
from util import auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Profiles(bot))


class Profiles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _create_profile(self, user: discord.User):
        """
        Creates a profile for given user. The caller has to guarantee that the
        user doesn't already have one.
        """
        profile = Profile(self.bot, user, None)

        query = """INSERT INTO profiles ("user", location) VALUES ($1, $2);"""
        await self.bot.pool.execute(query, *profile.to_tuple())

        return profile

    async def get_profile(self, user: discord.User):
        query = """SELECT *
                   FROM profiles
                   WHERE "user" = $1;"""
        row = await self.bot.pool.fetchrow(query, user.id)

        if not row:
            profile = await self._create_profile(user)
        else:
            profile = Profile.from_record(row, self.bot)

        return profile

    async def update(self, user: discord.User, item, new_value):
        if item not in Profile.ITEMS_DB:
            raise commands.BadArgument(f"Can't update {item}")

        query = f"""UPDATE profiles SET {item} = $1 WHERE "user" = $2;"""
        await self.bot.pool.execute(query, new_value, user.id)

    @auto_help
    @commands.group(invoke_without_command=True, brief="View or edit profiles")
    async def profile(self, ctx, user: discord.User = None):
        user = user or ctx.author
        profile = await self.get_profile(user)
        await ctx.send(embed=profile.to_embed())

    @profile.command(name="location")
    async def location(self, ctx, *, location: commands.clean_content):
        await self.update(ctx.author, "location", location)
        await ctx.send(f"Successfully set your location to `{location}`.")
