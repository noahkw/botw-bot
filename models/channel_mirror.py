from typing import Optional

import discord
from discord import Webhook
from sqlalchemy import Column, BigInteger, Boolean
from sqlalchemy.ext.hybrid import hybrid_property

from models.base import Base


class ChannelMirror(Base):
    __tablename__ = "channel_mirrors"

    _origin = Column(BigInteger, primary_key=True)
    _destination = Column(BigInteger, primary_key=True)
    _webhook = Column(BigInteger, nullable=True)
    enabled = Column(Boolean, default=True)
    _webhook_obj: Optional[Webhook] = None

    @hybrid_property
    def origin(self):
        return self.bot.get_channel(self._origin)

    @hybrid_property
    def destination(self):
        return self.bot.get_channel(self._destination)

    @hybrid_property
    async def webhook(self):
        if not self._webhook_obj:
            self._webhook_obj = await self.bot.fetch_webhook(self._webhook)

        return self._webhook_obj

    @webhook.setter
    def webhook(self, webhook: Webhook):
        self._webhook = webhook.id
        self._webhook_obj = webhook

    async def sanity_check(self):
        try:
            if (
                not await self.webhook
            ):  # notify owner that _webhook has been deleted; mirror dead
                await self.bot.get_user(self.bot.CREATOR_ID).send(
                    f"Mirror's _webhook has been deleted: {self}"
                )
        except discord.Forbidden:
            await self.bot.get_user(self.bot.CREATOR_ID).send(
                f"We don't have access to mirror's webhook (forbidden): "
                f"```origin: {self._origin}, dest: {self._destination}```"
            )
            return False
        except discord.NotFound:
            await self.bot.get_user(self.bot.CREATOR_ID).send(
                f"We don't have access to mirror's webhook (deleted): "
                f"```origin: {self._origin}, dest: {self._destination}```"
            )
            return False
        else:
            return True

    def __eq__(self, other):
        if not isinstance(other, ChannelMirror):
            return NotImplemented
        return self._origin == other._origin and self._destination == other._destination

    def __str__(self):
        return (
            f"channel mirror from {self.origin.mention}@`{self.origin.guild}` to "
            f"{self.destination.mention}@`{self.destination.guild}`"
        )

    @classmethod
    def inject_bot(cls, bot):
        cls.bot = bot
