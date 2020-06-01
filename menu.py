from discord import Embed
from discord.ext import menus

from const import CROSS_EMOJI, CHECK_EMOJI
from models import Tag


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
            name=f'Reactions - Page {menu.current_page + 1} / {self.get_max_pages()}',
            value='\n'.join([
                Tag.to_list_element(tag)
                for tag in entries
            ]))
        return embed


class ReminderListSource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=5)

    async def format_page(self, menu, entries):
        embed = Embed(title=f'Reminders - Page {menu.current_page + 1} / {self.get_max_pages()}')
        for reminder in entries:
            embed.add_field(**reminder.to_field())
        return embed


class BotwWinnerListSource(menus.ListPageSource):
    def __init__(self, data, winner_day):
        super().__init__(data, per_page=9)
        self.winner_day = winner_day

    async def format_page(self, menu, entries):
        embed = Embed(title=f'BotW Winners - Page {menu.current_page + 1} / {self.get_max_pages()}')
        for winner in entries:
            embed.add_field(**winner.to_field(self.winner_day))
        return embed
