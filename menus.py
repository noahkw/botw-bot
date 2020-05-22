from discord.ext import menus
from const import CROSS_EMOJI, CHECK_EMOJI


class Confirm(menus.Menu):
    def __init__(self, msg):
        super().__init__(timeout=60.0, delete_message_after=True)
        self.msg = msg
        self.result = None

    async def send_initial_message(self, ctx, channel):
        return await channel.send(self.msg)

    @menus.button(CHECK_EMOJI)
    async def do_confirm(self, payload):
        self.result = True
        self.stop()

    @menus.button(CROSS_EMOJI)
    async def do_deny(self, payload):
        self.result = False
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result
