import asyncio
import logging

import discord
from discord.ext import tasks

import db
from cogs import AinitMixin, CustomCog

from models import CustomRole

logger = logging.getLogger(__name__)


class CustomRoles(CustomCog, AinitMixin):
    def __index__(self, bot):
        super().__init__(bot)

        CustomRole.inject_bot(bot)

    async def _delete_custom_role(self, session, custom_role: CustomRole) -> None:
        try:
            await custom_role.role.delete(
                reason=f"Member {custom_role.member} ({custom_role.member.id}) removed their boost"
            )
            await db.delete_custom_role(session, custom_role._guild, custom_role._user)
        except discord.Forbidden:
            logger.info(
                "no permissions to delete custom role in %s (%d) for user %s (%d)",
                str(custom_role.guild),
                custom_role._guild,
                str(custom_role.member),
                custom_role._member,
            )

    @tasks.loop(hours=24.0)
    async def _role_removal_loop(self) -> None:
        async with self.bot.Session() as session:
            custom_roles = await db.get_custom_roles(session)

            role_deletion_tasks = []

            for custom_role in custom_roles:
                if custom_role.member.premium_since is None:
                    # member is no longer boosting, add to deletion list
                    role_deletion_tasks.append(
                        self._delete_custom_role(session, custom_role)
                    )

            await asyncio.gather(*custom_roles)
