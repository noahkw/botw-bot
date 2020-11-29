import enum

from sqlalchemy import Column, String, Integer, BigInteger, Boolean, Enum
from sqlalchemy.ext.hybrid import hybrid_property

from const import WEEKDAY_TO_INT
from models.base import Base, PendulumDateTime
from models.guild_settings import GuildSettingsMixin
from util import safe_mention


class BotwState(enum.Enum):
    DEFAULT = "DEFAULT"
    WINNER_CHOSEN = "WINNER_CHOSEN"
    SKIP = "SKIP"


class Idol(Base):
    __tablename__ = "idols"

    _idol = Column(Integer, primary_key=True)
    group = Column(String, nullable=False)
    name = Column(String, nullable=False)

    def __str__(self):
        return f"{self.group} {self.name}"

    def __eq__(self, other):
        if not isinstance(other, Idol):
            return NotImplemented
        return self.group == other.group and self.name == other.name


class NominationMixin:
    idol_group = Column(String, nullable=False)
    idol_name = Column(String, nullable=False)

    @hybrid_property
    def guild(self):
        return self.bot.get_guild(self._guild)

    @hybrid_property
    def member(self):
        return self.guild.get_member(self._member)

    @hybrid_property
    def idol(self):
        return Idol(group=self.idol_group, name=self.idol_name)

    @idol.setter
    def idol(self, idol: Idol):
        self.idol_group = idol.group
        self.idol_name = idol.name

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot


class Nomination(NominationMixin, Base):
    __tablename__ = "botw_nominations"

    _guild = Column(BigInteger, primary_key=True)
    _member = Column(BigInteger, primary_key=True)

    def __eq__(self, other):
        if not isinstance(other, Nomination):
            return NotImplemented
        return (
            self._member == other._member
            and self._guild == other._guild
            and self.idol_group == other.idol_group
            and self.idol_name == other.idol_name
        )

    def to_field(self):
        return {
            "name": str(self.member),
            "value": f"{self.idol_group} {self.idol_name}",
        }


class BotwWinner(NominationMixin, Base):
    __tablename__ = "botw_winners"

    _botw_winner = Column(Integer, primary_key=True)
    _guild = Column(BigInteger, nullable=False)
    _member = Column(BigInteger, nullable=False)
    date = Column(PendulumDateTime, default=PendulumDateTime.now())

    def __eq__(self, other):
        if not isinstance(other, BotwWinner):
            return NotImplemented
        return (
            self._member == other._member
            and self._guild == other._guild
            and self._idol == other._idol
            and self.date == other.date
        )

    def to_field(self, winner_day=None):
        week = (
            self.date.week_of_year
            if self.date.day_of_week < winner_day and self.date.day_of_week != 0
            else self.date.week_of_year + 1
        )
        year = self.date.year
        return {
            "name": f"{year}-{week}",
            "value": f"{self.idol} by {safe_mention(self.member)}",
        }


class BotwSettings(GuildSettingsMixin, Base):
    __tablename__ = "botw_settings"

    _botw_channel = Column(BigInteger)
    _nominations_channel = Column(BigInteger)
    enabled = Column(Boolean, default=True)
    winner_changes = Column(Boolean, default=False)
    state = Column("state", Enum(BotwState), default=BotwState.DEFAULT)
    announcement_day = Column(Integer, nullable=False)
    winner_day = Column(Integer, nullable=False)

    @hybrid_property
    def botw_channel(self):
        return self.bot.get_channel(self._botw_channel)

    @hybrid_property
    def nominations_channel(self):
        return self.bot.get_channel(self._nominations_channel)

    @property
    def announcement_day_str(self):
        return list(WEEKDAY_TO_INT.keys())[
            list(WEEKDAY_TO_INT.values()).index(self.announcement_day)
        ]

    @property
    def winner_day_str(self):
        return list(WEEKDAY_TO_INT.keys())[
            list(WEEKDAY_TO_INT.values()).index(self.winner_day)
        ]
