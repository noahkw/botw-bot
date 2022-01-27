import asyncio
import logging

import discord

from util import Cooldown, chunker


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
                text = "\n".join(self._queue)
                text_chunks = chunker(text, 1900)
                for text_chunk in text_chunks:
                    await self._destination.send(f"```\n{text_chunk}```")
                self._queue = []

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        asyncio.create_task(self.log_or_queue(msg))
