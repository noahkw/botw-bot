import asyncio

import discord


class ChannelLocker:
    def __init__(self):
        self._locks = {}

    async def get(self, messageable: discord.abc.Messageable):
        lock = self._locks.setdefault(
            (await messageable._get_channel()).id, asyncio.Lock()
        )
        return lock
