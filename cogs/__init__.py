import asyncio
import logging

from discord.ext.commands import Cog

logger = logging.getLogger(__name__)


class AinitMixin:
    def __init__(self):
        self._ready = asyncio.Event()
        if self.bot.loop.is_running():
            asyncio.create_task(self._ainit_and_ready())
        else:
            self.bot.loop.run_until_complete(self._ainit_and_ready())

    async def _ainit_and_ready(self):
        await self._ainit()
        self._ready.set()
        logger.info("Cog %s is ready", self.__class__.__name__)

    async def _ainit(self):
        """
        Override to do custom async initialization
        """

    async def wait_until_ready(self):
        await self._ready.wait()


class CustomCog(Cog):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()
