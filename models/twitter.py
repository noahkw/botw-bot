from sqlalchemy import Column, BigInteger, Integer, String, Boolean

from models.base import Base


class TwtSetting(Base):
    __tablename__ = "TwtSetting"

    _guild = Column(BigInteger, primary_key=True)
    use_group_channel = Column(Boolean, nullable=False)
    default_channel = Column(BigInteger, nullable=False)


class TwtAccount(Base):
    __tablename__ = "TwtAccount"

    _TwtAccount = Column(Integer, primary_key=True)
    _guild = Column(BigInteger, nullable=False)
    account_id = Column(String, nullable=False)


class TwtSorting(Base):
    __tablename__ = "TwtSorting"

    _TwtSorting = Column(Integer, primary_key=True)
    _guild = Column(BigInteger, nullable=False)
    hashtag = Column(String, nullable=False)
    _channel = Column(BigInteger, nullable=False)


class TwtFilter(Base):
    __tablename__ = "TwtFilter"

    _TwtFilter = Column(Integer, primary_key=True)
    _guild = Column(BigInteger, nullable=False)
    _filter = Column(String, nullable=False)
