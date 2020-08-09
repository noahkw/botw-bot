from typing import Optional

from discord import Webhook


class ChannelMirror:
    def __init__(self, bot, origin, destination, webhook, enabled=True):
        self._origin: int = origin
        self._destination: int = destination
        self._webhook: int = webhook
        self._webhook_obj: Optional[Webhook] = None
        self._enabled: int = enabled
        self._bot = bot

    @property
    def origin(self):
        return self._bot.get_channel(self._origin)

    @property
    def destination(self):
        return self._bot.get_channel(self._destination)

    @property
    async def webhook(self):
        if not self._webhook_obj:
            self._webhook_obj = await self._bot.fetch_webhook(self._webhook)

        return self._webhook_obj

    @webhook.setter
    def webhook(self, webhook: Webhook):
        self._webhook = webhook.id
        self._webhook_obj = webhook

    @property
    def enabled(self):
        return self._enabled

    def __eq__(self, other):
        if not isinstance(other, ChannelMirror):
            return NotImplemented
        return self._origin == other._origin and self._destination == other._destination

    @staticmethod
    async def from_record(source, bot):
        mirror = ChannelMirror(bot, **source)

        if not await mirror.webhook:  # notify owner that _webhook has been deleted; mirror dead
            await bot.get_user(bot.CREATOR_ID).send(f'Mirror\'s _webhook has been deleted: {mirror}')

        return mirror

    def __str__(self):
        return f'channel mirror from {self.origin.mention}@`{self.origin.guild}` to ' \
               f'{self.destination.mention}@`{self.destination.guild}`'

    def __repr__(self):
        return f'<ChannelMirror origin={repr(self._origin)} destination={repr(self._destination)} ' \
               f'webhook={repr(self._webhook)} _enabled={self._enabled}>'

    def to_tuple(self):
        return self._origin, self._destination, self._webhook, self._enabled
