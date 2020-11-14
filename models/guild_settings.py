from sqlalchemy import Column, String, BigInteger
from sqlalchemy.ext.hybrid import hybrid_property

from .base import Base


class GuildSettingsMixin:
    _guild = Column(BigInteger, primary_key=True)

    @hybrid_property
    def guild(self):
        return self.bot.get_guild(self._guild)

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot


class GuildSettings(GuildSettingsMixin, Base):
    __tablename__ = "guild_settings"
    prefix = Column(String)


class EmojiSettings(GuildSettingsMixin, Base):
    __tablename__ = "emoji_settings"
    _channel = Column(BigInteger, nullable=False)

    @hybrid_property
    def channel(self):
        return self.bot.get_channel(self._channel)
