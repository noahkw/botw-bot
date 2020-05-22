import math

from discord import Embed
from discord.ext import menus

from const import CROSS_EMOJI, CHECK_EMOJI
from models.Tag import Tag


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


class TagListSource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=10)

    async def format_page(self, menu, entries):
        embed = Embed(title='Tags')
        embed.add_field(
            name=f'Reactions - Page {menu.current_page + 1} / {self.number_pages(menu)}',
            value='\n'.join([
                Tag.to_list_element(tag)
                for tag in entries
            ]))
        return embed

    def number_pages(self, menu):
        return math.ceil(len(menu.source.entries) / self.per_page)
