import re
from datetime import datetime
import discord
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Integer,
    Boolean,
    DateTime,
    update,
    delete,
)
from sqlalchemy.ext.hybrid import hybrid_property

from util import safe_mention
from .base import Base

IMAGE_URL_REGEX = r"https?:\/\/.*\.(jpe?g|png|gif)"


class Tag(Base):
    __tablename__ = "tags"
    EDITABLE = ["trigger", "reaction", "in_msg"]

    tag_id = Column(Integer, primary_key=True)
    trigger = Column(String)
    reaction = Column(String)
    in_msg = Column(Boolean)
    _creator = Column(BigInteger)
    _guild = Column(BigInteger)
    use_count = Column(Integer, default=0)
    date = Column(DateTime, default=datetime.utcnow)

    @hybrid_property
    def creator(self):
        return self.bot.get_user(self._creator)

    @hybrid_property
    def guild(self):
        return self.bot.get_guild(self._guild)

    def __eq__(self, other):
        if not isinstance(other, Tag):
            return NotImplemented
        return (
            str.lower(self.trigger) == str.lower(other.trigger)
            and str.lower(self.reaction) == str.lower(other.reaction)
            and self._guild == other._guild
        )

    def to_list_element(self, index):
        return f"*{index + 1}*. `{self.tag_id}`: *{self.trigger}* by {self.creator}"

    def info_embed(self):
        embed = (
            discord.Embed(title=f"Tag `{self.tag_id}`")
            .add_field(name="Trigger", value=self.trigger)
            .add_field(name="Reaction", value=self.reaction)
            .add_field(name="Creator", value=safe_mention(self.creator))
            .add_field(name="Triggers in message", value=str(self.in_msg))
            .add_field(name="Use Count", value=str(self.use_count))
            .set_footer(text=f"Created on {self.date}")
        )

        if re.search(IMAGE_URL_REGEX, self.reaction):
            embed.set_image(url=self.reaction)

        return embed

    async def increment_use_count(self, session):
        self.use_count += 1
        statement = (
            update(Tag)
            .where(Tag.tag_id == self.tag_id)
            .values(use_count=self.use_count)
        )
        await session.execute(statement)

    async def delete(self, session):
        statement = delete(Tag).where(Tag.tag_id == self.tag_id)
        await session.execute(statement)

    async def update(self, session, key, value):
        setattr(self, key, value)
        statement = update(Tag).where(Tag.tag_id == self.tag_id).values({key: value})
        await session.execute(statement)

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot
