import asyncio
import logging

from discord.ext import commands
from dateparser import parse

from models import Reminder

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Reminders(bot))


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders_collection = self.bot.config['reminders']['reminders_collection']

        if self.bot.loop.is_running():
            asyncio.create_task(self._ainit())
        else:
            self.bot.loop.run_until_complete(self._ainit())

    async def _ainit(self):
        self.reminders = [Reminder.from_dict(reminder.to_dict(), self.bot, reminder.id) for reminder in
                          await self.bot.db.get(self.reminders_collection)]

        logger.info(f'# Initial reminders from db: {len(self.reminders)}')

    @commands.group(name='reminders', aliases=['remindme', 'remind'], invoke_without_command=True)
    async def reminders_(self, ctx, when: str = None, what: commands.clean_content = None):
        if when and what:
            await ctx.invoke(self.add, when, what)
        else:
            await ctx.send_help(self.reminders_)

    @reminders_.command()
    async def add(self, ctx, when: str, what: commands.clean_content):
        """
        Adds a new reminder
        Example usage:
        .remind in 3 hours to do the laundry
        .remind 15-06-20 at 6pm KST to Irene & Seulgi debut
        .remind in 6 minutes 30 seconds to eggs
        """
        parsed_date = parse(when)
        if parsed_date is None:
            raise commands.BadArgument('Couldn\'t parse the date.')

        await ctx.send(f'I\'ll remind you at {parsed_date} to {what}.')

    @add.error
    @reminders_.error
    async def add_error(self, ctx, error):
        if isinstance(error, commands.BadArgument) or isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(error)
        else:
            logger.error(error)

    @reminders_.command()
    async def list(self, ctx):
        """
        Lists your reminders
        """
        await ctx.send('Your reminders:')
