from discord import Member
from sqlalchemy import Column, BigInteger
from sqlalchemy.ext.hybrid import hybrid_property

from models.base import Base
from models.guild_settings import GuildSettingsMixin


class BlockedUser(GuildSettingsMixin, Base):
    __tablename__ = "blocked_users"

    _user = Column(BigInteger, primary_key=True)

    @hybrid_property
    def member(self) -> Member:
        return self.guild.get_member(self._user)
