import pendulum
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    Boolean,
    Text,
)
from sqlalchemy.ext.hybrid import hybrid_property

from .base import Base, PendulumDateTime


class Reminder(Base):
    __tablename__ = "reminders"

    reminder_id = Column(Integer, primary_key=True)
    _user = Column(BigInteger, nullable=False)
    due = Column(PendulumDateTime, nullable=False)
    created = Column(PendulumDateTime, default=PendulumDateTime.now())
    done = Column(Boolean, default=False)
    content = Column(Text, nullable=False)

    @hybrid_property
    def user(self):
        return self.bot.get_user(self._user)

    def is_due(self):
        return self.due < pendulum.now("UTC")

    def __eq__(self, other):
        if not isinstance(other, Reminder):
            return NotImplemented
        return self.reminder_id == other.reminder_id

    def to_field(self):
        return {"name": self.due, "value": self.content}

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot
