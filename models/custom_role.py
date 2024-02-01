from sqlalchemy import Column, BigInteger
from sqlalchemy.ext.hybrid import hybrid_property

from models.base import Base
from models.guild_settings import GuildSettingsMixin
from models.role import RoleMixin


from discord import Member, Role


class CustomRole(RoleMixin, Base):
    __tablename__ = "custom_roles"

    _role = Column(BigInteger, nullable=False)
    _guild = Column(BigInteger, primary_key=True)
    _user = Column(BigInteger, primary_key=True)

    @hybrid_property
    def member(self) -> Member:
        return self.guild.get_member(self._user)


class CustomRoleSettings(GuildSettingsMixin, Base):
    __tablename__ = "custom_role_settings"

    """The role that gets to create custom roles/is the insertion point"""
    _role = Column(BigInteger, nullable=False)

    @hybrid_property
    def role(self) -> Role:
        return self.guild.get_role(self._role)
