from sqlalchemy import Column, BigInteger, Integer, String

from models.base import Base


class TwtSettings(Base):
    __tablename__ = "twt_settings"

    _guild = Column(BigInteger, primary_key=True)
    default_channel = Column(BigInteger, nullable=False)


class TwtAccounts(Base):
    __tablename__ = "twt_accounts"

    server_account_id = Column(Integer, primary_key=True)
    _guild = Column(BigInteger, nullable=False)
    account_id = Column(String, nullable=False)


class TwtFilters(Base):
    __tablename__ = "twt_filters"

    server_channel_id = Column(Integer, primary_key=True)
    _guild = Column(BigInteger, nullable=False)
    hashtag = Column(String, nullable=False)
    _channel = Column(BigInteger, nullable=False)
