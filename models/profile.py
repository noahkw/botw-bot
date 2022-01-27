import pendulum
from discord import Embed
from sqlalchemy import Column, BigInteger, String, update
from sqlalchemy.ext.hybrid import hybrid_property

from models.base import Base


class Profile(Base):
    __tablename__ = "profiles"
    EDITABLE = frozenset(["location"])

    _user = Column(BigInteger, primary_key=True)
    location = Column(String, nullable=True)

    @hybrid_property
    def user(self):
        return self.bot.get_user(self._user)

    def to_embed(self):
        embed = Embed(title=f"Profile of {self.user}")

        embed.set_image(url=self.user.avatar.url)
        embed.add_field(
            name="Joined Discord",
            value=pendulum.instance(self.user.created_at).to_cookie_string(),
        )
        return embed

    async def update(self, session, key, value):
        setattr(self, key, value)
        statement = (
            update(Profile).where(Profile._user == self._user).values({key: value})
        )
        await session.execute(statement)

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot
