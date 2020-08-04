import logging
import re
from datetime import timezone

import pendulum
from aioscheduler import TimedScheduler
from dateparser import parse
from discord.ext import commands
from discord.ext.menus import MenuPages
from discord.utils import find

from cogs import CustomCog, AinitMixin
from const import SHOUT_EMOJI, SNOOZE_EMOJI
from menu import ReminderListSource, SimpleConfirm
from models import Reminder
from util import has_passed, auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Reminders(bot))


class ReminderConverter(commands.Converter):
    async def convert(self, ctx, argument):
        # match strings like 'in 1 hour to do the laundry'
        r_to = re.search(r'(.*?) to (.*)', argument, re.DOTALL)
        if r_to:
            return r_to.group(1), r_to.group(2)

        # match strings like '"28-05-20 at 18:00 KST" "Red Velvet comeback"'
        # may be improved to also parse the forms '"longer string" singleword'
        # and 'singleword "longer string"'
        r_quotes = re.search(r'"(.*)" *"(.*)"', argument, re.DOTALL)
        if r_quotes:
            return r_quotes.group(1), r_quotes.group(2)

        # match strings like 'tomorrow football'
        tokens = argument.split()
        return tokens[0], tokens[1]


def parse_date(date):
    parsed_date = parse(date)
    if parsed_date is None:
        raise commands.BadArgument('Couldn\'t parse the date.')
    if parsed_date.tzinfo is None:
        parsed_date = parsed_date.astimezone(timezone.utc)

    parsed_date = pendulum.parse(str(parsed_date))
    # add 1s to account for processing time, results in nicer diffs
    parsed_date = parsed_date.add(seconds=1)

    if has_passed(parsed_date):
        raise commands.BadArgument(f'`{parsed_date.to_cookie_string()}` is in the past.')

    return parsed_date


class Reminders(CustomCog, AinitMixin):
    def __init__(self, bot):
        super().__init__(bot)
        self.reminders_collection = self.bot.config['reminders']['reminders_collection']
        self.scheduler = TimedScheduler(prefer_utc=True)
        self.scheduler.start()
        self.shout_emoji = find(lambda e: e.name == SHOUT_EMOJI, self.bot.emojis)

        super(AinitMixin).__init__()

    async def _ainit(self):
        self.reminders = [Reminder.from_dict(reminder.to_dict(), self.bot, reminder.id) for reminder in
                          await self.bot.db.get(self.reminders_collection)]
        self.reminders = [reminder for reminder in self.reminders if not reminder.done]
        for reminder in self.reminders:
            if has_passed(reminder.due):
                await self.remind_user(reminder, late=True)
            else:
                self.scheduler.schedule(self.remind_user(reminder), reminder.due)

        logger.info(f'# Initial reminders from db: {len(self.reminders)}')

    def cog_unload(self):
        self.scheduler._task.cancel()

    @auto_help
    @commands.group(name='reminders', aliases=['remindme', 'remind'], invoke_without_command=True,
                    brief='Set reminders in the future')
    async def reminders_(self, ctx, *, args: ReminderConverter = None):
        if args:
            await ctx.invoke(self.add, args=args)
        else:
            await ctx.send_help(self.reminders_)

    @reminders_.command(brief='Adds a new reminder')
    async def add(self, ctx, *, args: ReminderConverter):
        """
        Adds a new reminder.

        Example usage:
        `{prefix}remind in 3 hours to do the laundry`
        `{prefix}remind 15-06-20 at 6pm KST to Irene & Seulgi debut`
        `{prefix}remind in 6 minutes 30 seconds to eggs`
        """
        when, what = args
        parsed_date = parse_date(when)

        now = pendulum.now('UTC')
        diff = parsed_date.diff_for_humans(now, True)

        reminder = Reminder(None, ctx.author, parsed_date, now, what)
        id_ = await self.bot.db.set_get_id(self.reminders_collection, reminder.to_dict())
        reminder.id = id_
        self.reminders.append(reminder)
        self.scheduler.schedule(self.remind_user(reminder), parsed_date)

        await ctx.send(f'I\'ll remind you on `{parsed_date.to_cookie_string()}` (in {diff}): `{what}`.')

    @reminders_.command()
    async def list(self, ctx):
        """
        Lists your reminders
        """
        user_reminders = [reminder for reminder in self.reminders if reminder.user == ctx.author and not reminder.done]
        if len(user_reminders) > 0:
            pages = MenuPages(source=ReminderListSource(user_reminders), clear_reactions_after=True)
            await pages.start(ctx)
        else:
            await ctx.send('You have 0 pending reminders!')

    async def remind_user(self, reminder, late=False):
        diff = reminder.created.diff_for_humans(reminder.due, True)
        assert not reminder.done

        user = reminder.user

        if late:
            await user.send(f'{self.shout_emoji} You told me to remind you some time ago. '
                            f'Sorry for being late:\n{reminder.content}')
        else:
            message = await user.send(f'{self.shout_emoji} You told me to remind you {diff} ago:\n{reminder.content}')
            ctx = await self.bot.get_context(message)
            ctx.author = user

            confirm = await SimpleConfirm(message, timeout=120.0, emoji=SNOOZE_EMOJI).prompt(ctx)
            if confirm:
                try:
                    new_due = await self.prompt_snooze_time(reminder)
                    reminder.due = new_due
                    await self.bot.db.update(self.reminders_collection, reminder.id, {'due': new_due.timestamp()})
                    self.scheduler.schedule(self.remind_user(reminder), new_due)
                    return
                except commands.BadArgument as ba:
                    await ctx.send(ba)

        reminder.done = True
        await self.bot.db.update(self.reminders_collection, reminder.id, {'done': True})

    async def prompt_snooze_time(self, reminder):
        user = reminder.user

        message = await user.send('When do you want me to remind you again? (e.g.: `in 30 minutes`)')
        channel = message.channel

        answer = await self.bot.wait_for('message', check=lambda msg: msg.channel == channel)
        parsed_date = parse_date(answer.content)

        now = pendulum.now('UTC')
        diff = parsed_date.diff_for_humans(now, True)

        await channel.send(f'Reminding you again in {diff}.')
        return parsed_date
