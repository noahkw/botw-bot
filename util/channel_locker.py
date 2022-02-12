import typing
from asyncio import Lock

from discord.abc import Messageable


class ChannelLocker:
    def __init__(self):
        self._locks: typing.Dict[int, Lock] = {}

    async def get(self, messageable: Messageable) -> Lock:
        lock = self._locks.setdefault((await messageable._get_channel()).id, Lock())
        return lock
