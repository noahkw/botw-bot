import enum

from sqlalchemy import Column, BigInteger, String, Enum
from sqlalchemy.ext.hybrid import hybrid_property

from models.base import Base


class GreeterType(enum.Enum):
    JOIN = "join"
    LEAVE = "leave"

    def __str__(self):
        return self.value.capitalize()


class Greeter(Base):
    __tablename__ = "greeters"

    _guild = Column(BigInteger, primary_key=True)
    _channel = Column(BigInteger, nullable=False)
    template = Column(String)
    type = Column(Enum(GreeterType), primary_key=True)

    @hybrid_property
    def guild(self):
        return self.bot.get_guild(self._guild)

    @hybrid_property
    def channel(self):
        return self.bot.get_channel(self._channel)

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot
