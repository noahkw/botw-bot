from sqlalchemy import Column, BigInteger, String, Integer, Text
from sqlalchemy.ext.hybrid import hybrid_property

from models.base import Base, PendulumDateTime


class CommandLog(Base):
    __tablename__ = "command_logs"

    _command_log = Column(Integer, primary_key=True)
    command_name = Column(String, nullable=False)
    cog = Column(String, nullable=False)
    _user = Column(BigInteger, nullable=False)
    _guild = Column(BigInteger, nullable=False)
    date = Column(PendulumDateTime, default=PendulumDateTime.now())
    args = Column(Text)

    @hybrid_property
    def user(self):
        return self.bot.get_user(self._user)

    @hybrid_property
    def guild(self):
        return self.bot.get_guild(self._guild)

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot
