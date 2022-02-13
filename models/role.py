import pendulum
from sqlalchemy import Column, BigInteger, Integer, Boolean, ForeignKey, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from models.base import Base, PendulumDateTime
from models.guild_settings import GuildSettingsMixin


class RoleMixin:
    @hybrid_property
    def role(self):
        return self.guild.get_role(self._role)

    @hybrid_property
    def guild(self):
        return self.bot.get_guild(self._guild)

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot


class AssignableRole(RoleMixin, Base):
    __tablename__ = "roles"

    _role = Column(BigInteger, primary_key=True)
    _guild = Column(BigInteger, nullable=False)
    clear_after = Column(Integer)
    enabled = Column(Boolean, default=True)
    aliases = relationship(
        "RoleAlias", lazy="selectin", cascade="all, delete", passive_deletes=True
    )


class RoleAlias(RoleMixin, Base):
    __tablename__ = "role_aliases"

    _role = Column(ForeignKey(AssignableRole._role, ondelete="CASCADE"), nullable=False)
    _guild = Column(BigInteger, primary_key=True)
    alias = Column(String, primary_key=True)

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot


class RoleClear(RoleMixin, Base):
    __tablename__ = "role_clears"

    _role = Column(BigInteger, primary_key=True)
    _member = Column(BigInteger, primary_key=True)
    _guild = Column(BigInteger, nullable=False)
    when = Column(PendulumDateTime, nullable=False)

    @hybrid_property
    def member(self):
        return self.guild.get_member(self._member)

    def is_due(self):
        return self.when < pendulum.now("UTC")

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot


class RoleSettings(GuildSettingsMixin, Base):
    __tablename__ = "role_settings"

    _auto_role = Column(BigInteger, nullable=True)

    @hybrid_property
    def auto_role(self):
        return self.guild.get_role(self._auto_role)
