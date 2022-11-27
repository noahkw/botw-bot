import logging
from functools import wraps

import discord
import gfypy
from discord import Embed
from discord.ext import menus, commands

from const import NUMBER_TO_EMOJI, UNICODE_EMOJI
from util import cmd_to_str

logger = logging.getLogger(__name__)


def react_on_forbidden(coro):
    @wraps(coro)
    async def wrapped(self, ctx: commands.Context, *args, **kwargs):
        try:
            await coro(self, ctx, *args, **kwargs)
        except menus.CannotSendMessages:
            try:
                await ctx.message.add_reaction(UNICODE_EMOJI["CROSS"])
            except discord.Forbidden:
                logger.info("Could neither respond nor react in '%s'", ctx.channel.id)

    return wrapped


class Confirm(menus.Menu):
    def __init__(self, msg):
        super().__init__(timeout=60.0, delete_message_after=True)
        self.msg = msg
        self.result = None

    async def send_initial_message(self, ctx, channel):
        return await channel.send(self.msg)

    @menus.button(UNICODE_EMOJI["CHECK"])
    async def do_confirm(self, payload):
        self.result = True
        self.stop()

    @menus.button(UNICODE_EMOJI["CROSS"])
    async def do_deny(self, payload):
        self.result = False
        self.stop()

    @react_on_forbidden
    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result


class SimpleConfirm(menus.Menu):
    def __init__(self, msg, timeout=60.0, emoji=UNICODE_EMOJI["CHECK"]):
        super().__init__(timeout=timeout, clear_reactions_after=True)
        self.msg = msg
        self.result = None

        def button_callback():
            async def do_confirm(_, payload):
                self.result = True
                self.stop()

            return do_confirm

        button = menus.Button(emoji, button_callback())
        self.add_button(button)

    async def send_initial_message(self, ctx, channel):
        return self.msg

    @react_on_forbidden
    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result


class EmbedHelpCommandListSource(menus.ListPageSource):
    def __init__(self, embed, data, per_page):
        super().__init__(data, per_page=per_page)
        self.embed: Embed = embed
        self.fields = len(embed.fields) + 1
        self.field_to_remove = len(embed.fields)

    async def format_page(self, menu, entries):
        if len(self.embed.fields) == self.fields:
            self.embed.remove_field(self.field_to_remove)

        self.embed.add_field(
            name=f"Subcommands - Page {menu.current_page + 1} / {self.get_max_pages()}",
            value=" ".join(map(cmd_to_str(), entries)),
            inline=False,
        )

        return self.embed


class CommandUsageListSource(menus.ListPageSource):
    def __init__(self, data, by, command_name, weeks, per_page=10):
        super().__init__(data, per_page=per_page)
        self.by = by
        self.command_name = command_name
        self.weeks = weeks

    async def format_page(self, menu, entries):
        get_func = menu.bot.get_user if self.by == "user" else menu.bot.get_guild

        embed = Embed(title="Command Usage")
        embed.add_field(
            name=f"Usages of command **{self.command_name}** in the past {self.weeks} week(s)",
            value="\n".join(
                f"{get_func(usage[0])} (`{usage[0]}`): **{usage[2]}**"
                for usage in entries
            ),
        )

        return embed


class TwitterListSource(menus.ListPageSource):
    def __init__(self, data, name, per_page=10):
        super().__init__(data, per_page=per_page)
        self.name = name

    async def format_page(self, menu, entries):
        embed = Embed()
        embed.add_field(
            name=f"{self.name} - Page {menu.current_page + 1} / {self.get_max_pages()}",
            value="\n".join(entries),
        )
        return embed


class TagListSource(menus.ListPageSource):
    def __init__(self, data, per_page=10):
        super().__init__(data, per_page=per_page)

    async def format_page(self, menu, entries):
        embed = Embed(title="Tags")
        embed.add_field(
            name=f"Reactions - Page {menu.current_page + 1} / {self.get_max_pages()}",
            value="\n".join(
                [tag.to_list_element(index) for index, tag in enumerate(entries)]
            ),
        )
        return embed


class DetailTagListSource(menus.ListPageSource):
    def __init__(self, data, per_page=1):
        super().__init__(data, per_page=per_page)

    async def format_page(self, menu, entry):
        embed = entry.info_embed()
        embed.title = (
            f"Tag `{entry.tag_id}` ({menu.current_page + 1} / {self.get_max_pages()})"
        )

        return embed


class ReminderListSource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=5)

    async def format_page(self, menu, entries):
        embed = Embed(
            title=f"Reminders - Page {menu.current_page + 1} / {self.get_max_pages()}"
        )
        for reminder in entries:
            embed.add_field(**reminder.to_field())
        return embed


class BotwWinnerListSource(menus.ListPageSource):
    def __init__(self, data, winner_day):
        super().__init__(data, per_page=9)
        self.winner_day = winner_day

    async def format_page(self, menu, entries):
        embed = Embed(
            title=f"BotW Winners - Page {menu.current_page + 1} / {self.get_max_pages()}"
        )
        for winner in entries:
            embed.add_field(**winner.to_field(self.winner_day))
        return embed


class NominationListSource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=12)

    async def format_page(self, menu, entries):
        embed = Embed(
            title=f"BotW Nominations - Page {menu.current_page + 1} / {self.get_max_pages()}"
        )
        for nomination in entries:
            embed.add_field(**nomination.to_field())
        return embed


class IdolListSource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=4)

    async def format_page(self, menu, entries):
        embed = Embed(title="Possible combinations")
        for index, combination in enumerate(entries):
            embed.add_field(name=str(index + 1), value=str(combination))
        return embed


class GfyListSource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=1)

    async def format_page(self, menu, entries):
        content = f"""**Gfy** `{menu.current_page + 1} / {self.get_max_pages()}`

**{entries['title']}**
**Views**: `{entries['views']}` | **Likes**: `{entries['likes']}`
{gfypy.const.GFYCAT_URL}/{entries['gfyId']}"""

        return content


class GfySourceEmpty(Exception):
    pass


class AsyncGfySource(menus.AsyncIteratorPageSource):
    def __init__(self, iter):
        super().__init__(iter, per_page=1)

    async def _iterate(self, n):
        it = self.iterator
        cache = self._cache
        for i in range(0, n):
            try:
                elem = await it.__anext__()
            except StopAsyncIteration:
                if i != 0:
                    self._exhausted = True
                else:
                    raise GfySourceEmpty
            else:
                cache.append(elem)

    async def format_page(self, menu, entry):
        content = f"""**Gfy** `{menu.current_page + 1} / ∞`

**{entry.title}**
**Views**: `{entry.views}` | **Likes**: `{entry.likes}`
{gfypy.const.GFYCAT_URL}/{entry.gfy_id}"""

        return content


class SelectionMenu(menus.MenuPages):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selection = None

        def action_maker(selection_num):
            async def action(_, payload):
                page = await self.source.get_page(self.current_page)
                self.selection = page[selection_num - 1]
                self.stop()

            return action

        for i in range(1, self.source.per_page + 1):
            button = menus.Button(
                NUMBER_TO_EMOJI[i], action_maker(i), position=menus.Last(1)
            )
            self.add_button(button)

    def _skip_double_triangle_buttons(self):
        max_pages = self._source.get_max_pages()
        if max_pages is None:
            return True
        return max_pages <= 2

    def _skip_paginating_buttons(self):
        return not self._source.is_paginating()

    @menus.button(
        "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
        position=menus.First(0),
        skip_if=_skip_double_triangle_buttons,
    )
    async def go_to_first_page(self, payload):
        """go to the first page"""
        await self.show_page(0)

    @menus.button(
        "\N{BLACK LEFT-POINTING TRIANGLE}\ufe0f",
        position=menus.First(1),
        skip_if=_skip_paginating_buttons,
    )
    async def go_to_previous_page(self, payload):
        """go to the previous page"""
        await self.show_checked_page(self.current_page - 1)

    @menus.button(
        "\N{BLACK RIGHT-POINTING TRIANGLE}\ufe0f",
        position=menus.Last(0),
        skip_if=_skip_paginating_buttons,
    )
    async def go_to_next_page(self, payload):
        """go to the next page"""
        await self.show_checked_page(self.current_page + 1)

    @menus.button(
        "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
        position=menus.Last(1),
        skip_if=_skip_double_triangle_buttons,
    )
    async def go_to_last_page(self, payload):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(self._source.get_max_pages() - 1)

    @menus.button("\N{BLACK SQUARE FOR STOP}\ufe0f", position=menus.Last(0))
    async def stop_pages(self, payload):
        """stops the pagination session."""
        self.stop()

    def is_paginating(self):
        return self.selection is None

    def should_add_reactions(self):
        return self.selection is None

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        await self.message.delete()
        return self.selection


class PseudoMenu:
    """
    Exhausts the source without user interaction and sends each page to the specified channel instantly.
    """

    def __init__(self, source, channel):
        self.current_page = 1
        self._source = source
        self._channel = channel

    async def show_page(self, page_number):
        page = await self._source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        await self._channel.send(**kwargs)

    async def _get_kwargs_from_page(self, page):
        value = await discord.utils.maybe_coroutine(
            self._source.format_page, self, page
        )
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value, "embed": None}
        elif isinstance(value, Embed):
            return {"embed": value, "content": None}

    async def start(self):
        await self._source._prepare_once()
        for i in range(self._source.get_max_pages()):
            await self.show_page(i)
