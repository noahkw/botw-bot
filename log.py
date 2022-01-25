import asyncio
import logging

import discord

from util import Cooldown


class MessageableHandler(logging.Handler):
    def __init__(self, destination: discord.abc.Messageable, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._destination = destination
        self._cooldown = Cooldown(3)
        self._queue = []

    async def log_or_queue(self, msg):
        self._queue.append(msg)

        if self._cooldown.cooldown:
            return
        else:
            async with self._cooldown:
                await self._destination.send("```\n" + "\n".join(self._queue) + "```")
                self._queue = []

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        asyncio.create_task(self.log_or_queue(msg))
