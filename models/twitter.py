from sqlalchemy import Column, BigInteger, String, Boolean
from sqlalchemy.ext.hybrid import hybrid_property

from models.base import Base


class TwitterMixin:
    _guild = Column(BigInteger, primary_key=True)

    @hybrid_property
    def guild(self):
        return self.bot.get_guild(self._guild)

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot


class TwtSetting(TwitterMixin, Base):
    __tablename__ = "twt_settings"

    use_group_channel = Column(Boolean, nullable=False)
    default_channel = Column(BigInteger, nullable=False)
    enabled = Column(Boolean, nullable=False)

    @hybrid_property
    def channel(self):
        return self.bot.get_channel(self.default_channel)


class TwtAccount(TwitterMixin, Base):
    __tablename__ = "twt_accounts"

    account_id = Column(String, primary_key=True)


class TwtSorting(TwitterMixin, Base):
    __tablename__ = "twt_sortings"

    hashtag = Column(String, primary_key=True)
    _channel = Column(BigInteger, nullable=False)

    @hybrid_property
    def channel(self):
        return self.bot.get_channel(self._channel)


class TwtFilter(TwitterMixin, Base):
    __tablename__ = "twt_filters"

    _filter = Column(String, primary_key=True)
