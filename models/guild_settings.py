from sqlalchemy import Column, String, BigInteger

from .base import Base


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    guild_id = Column(BigInteger, primary_key=True)
    prefix = Column(String)
