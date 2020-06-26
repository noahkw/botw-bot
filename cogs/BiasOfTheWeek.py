import asyncio
import logging
import random

import discord
import pendulum
from discord.ext import commands, tasks
from discord.ext.menus import MenuPages

from const import CROSS_EMOJI, CHECK_EMOJI
from menu import Confirm, BotwWinnerListSource
from models import BotwWinner, BotwState
from models import Idol

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(BiasOfTheWeek(bot))


def has_winner_role():
    def predicate(ctx):
        return ctx.bot.config['biasoftheweek']['winner_role_name'] in [role.name for role in ctx.message.author.roles]

    return commands.check(predicate)


class BiasOfTheWeek(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.nominations = {}
        self.nominations_collection = self.bot.config['biasoftheweek']['nominations_collection']
        self.past_winners_collection = self.bot.config['biasoftheweek']['past_winners_collection']
        self.past_winners_time = int(self.bot.config['biasoftheweek']['past_winners_time'])
        self.winner_day = int(self.bot.config['biasoftheweek']['winner_day'])
        self.announcement_day = divmod((self.winner_day - 3), 7)[1]
        self.botw_channel = self.bot.get_channel(int(self.bot.config['biasoftheweek']['botw_channel']))
        self.nominations_channel = self.bot.get_channel(int(self.bot.config['biasoftheweek']['nominations_channel']))
        self.skip_next = False

        if self.bot.loop.is_running():
            asyncio.create_task(self._ainit())
        else:
            self.bot.loop.run_until_complete(self._ainit())

    async def _ainit(self):
        _nominations = await self.bot.db.get(self.nominations_collection)

        for nomination in _nominations:
            self.nominations[self.bot.get_user(int(nomination.id))] = Idol.from_dict(nomination.to_dict())

        logger.info(f'Initial nominations from db: {self.nominations}')

        self.past_winners = [BotwWinner.from_dict(winner.to_dict(), self.bot) for winner in
                             await self.bot.db.get(self.past_winners_collection)]

        self._loop.start()

    @commands.group(name='biasoftheweek', aliases=['botw'])
    async def biasoftheweek(self, ctx):
        pass

    @biasoftheweek.command()
    async def nominate(self, ctx, group: commands.clean_content, name: commands.clean_content):
        idol = Idol(group, name)

        if idol in self.nominations.values():
            await ctx.send(f'**{idol}** has already been nominated. Please nominate someone else.')
        elif idol in [winner.idol for winner in self.past_winners if winner.timestamp > pendulum.now().subtract(
                days=self.past_winners_time)]:  # check whether idol has won in the past
            await ctx.send(
                f'**{idol}** has already won in the past `{self.past_winners_time}` days. Please nominate someone else.')
        elif ctx.author in self.nominations.keys():
            old_idol = self.nominations[ctx.author]

            confirm = await Confirm(f'Your current nomination is **{old_idol}**. Do you want to override it?').prompt(
                ctx)

            if confirm:
                self.nominations[ctx.author] = idol
                await self.bot.db.set(self.nominations_collection, str(ctx.author.id), idol.to_dict())
                await ctx.send(f'{ctx.author} nominates **{idol}** instead of **{old_idol}**.')
        else:
            self.nominations[ctx.author] = idol
            await self.bot.db.set(self.nominations_collection, str(ctx.author.id), idol.to_dict())
            await ctx.send(f'{ctx.author} nominates **{idol}**.')

    async def _clear_nominations(self, member=None):
        if member is None:
            self.nominations = {}
            await self.bot.db.delete(self.nominations_collection)
        else:
            self.nominations.pop(member)
            await self.bot.db.delete(self.nominations_collection, document=str(member.id))

    @biasoftheweek.command(name='clearnominations')
    @commands.has_permissions(administrator=True)
    async def clear_nominations(self, ctx, member: discord.Member = None):
        await self._clear_nominations(member)
        await ctx.message.add_reaction(CHECK_EMOJI)

    @biasoftheweek.command()
    async def nominations(self, ctx):
        if len(self.nominations) > 0:
            embed = discord.Embed(title='Bias of the Week nominations')
            for key, value in self.nominations.items():
                embed.add_field(name=key, value=value)

            await ctx.send(embed=embed)
        else:
            await ctx.send('So far, no idols have been nominated.')

    @biasoftheweek.command()
    @commands.has_permissions(administrator=True)
    async def winner(self, ctx, silent: bool = False):
        await self._pick_winner(silent=silent)

    async def _pick_winner(self, silent=False):
        member, pick = random.choice(list(self.nominations.items()))

        # Assign BotW winner role on next wednesday at 00:00 UTC
        now = pendulum.now('UTC')
        assign_date = now.next(self.winner_day)

        await self.nominations_channel.send(
            f"""Bias of the Week ({now.week_of_year}-{now.year}): {member if silent else member.mention}\'s pick **{pick}**. 
You will be assigned the role *{self.bot.config['biasoftheweek']['winner_role_name']}* on {assign_date.to_cookie_string()}.""")

        botw_winner = BotwWinner(member, pick, now)
        self.past_winners.append(botw_winner)
        await self.bot.db.add(self.past_winners_collection, botw_winner.to_dict())
        await self._clear_nominations(member)

    async def _assign_winner_role(self, winner):
        member = winner.member
        logger.info(f'Assigning winner role to {member}')
        guild = self.nominations_channel.guild
        member = guild.get_member(member.id)
        botw_winner_role = discord.utils.get(guild.roles, name=self.bot.config['biasoftheweek']['winner_role_name'])
        await member.add_roles(botw_winner_role)
        await member.send(f'Hi, your pick **{winner.idol}** won this week\'s BotW. Congratulations!\n'
                          f'You may now post your pics and gfys in {self.botw_channel.mention}.\n'
                          f'Don\'t forget to change the server icon using `.botw icon`'
                          f' in {self.nominations_channel.mention}.')

    async def _remove_winner_role(self, winner):
        member = winner.member
        logger.info(f'Removing winner role from {member}')
        guild = self.nominations_channel.guild
        member = guild.get_member(member.id)
        botw_winner_role = discord.utils.get(guild.roles, name=self.bot.config['biasoftheweek']['winner_role_name'])
        await member.remove_roles(botw_winner_role)

    @biasoftheweek.command()
    @commands.is_owner()
    async def skip(self, ctx):
        settings_cog = self.bot.get_cog('Settings')
        settings = await settings_cog.get_settings(ctx.guild)
        state = settings.botw_state
        if state == BotwState.WINNER_CHOSEN:
            raise commands.BadArgument('Can\'t skip because the current winner has not been notified yet.')

        await settings_cog.set_botw_state(ctx.guild, BotwState.DEFAULT if state == BotwState.SKIP else BotwState.SKIP)

        next_announcement = pendulum.now('UTC').next(self.announcement_day)
        await ctx.send(f'BotW Winner selection on {next_announcement.to_cookie_string()} is '
                       f'now {"" if state == BotwState.DEFAULT else "not "}being skipped.')

    @tasks.loop(hours=1.0)
    async def _loop(self):
        # pendulum.set_test_now(pendulum.now('UTC').next(self.winner_day))
        logger.info('Hourly loop running')
        now = pendulum.now('UTC')
        guild = self.nominations_channel.guild
        settings_cog = self.bot.get_cog('Settings')
        settings = await settings_cog.get_settings(guild)

        # pick winner on announcement day
        if now.day_of_week == self.announcement_day and now.hour == 0:
            if settings.botw_state not in (BotwState.SKIP, BotwState.WINNER_CHOSEN) and len(self.nominations) > 0:
                await self._pick_winner()
                await settings_cog.set_botw_state(guild, BotwState.WINNER_CHOSEN)
            else:
                logger.info(f'Skipping BotW winner selection in {guild}')

        # assign role on winner day
        elif now.day_of_week == self.winner_day and now.hour == 0:
            if settings.botw_state not in (BotwState.SKIP, BotwState.DEFAULT):
                winner, previous_winner = sorted(self.past_winners, key=lambda w: w.timestamp, reverse=True)[0:2]
                await self._remove_winner_role(previous_winner)
                await self._assign_winner_role(winner)
            else:
                logger.info(f'Skipping BotW winner role assignment in {guild}')

            await settings_cog.set_botw_state(guild, BotwState.DEFAULT)

    @_loop.before_loop
    async def loop_before(self):
        await self.bot.wait_until_ready()

    @biasoftheweek.command()
    async def history(self, ctx):
        if len(self.past_winners) > 0:
            past_winners = sorted(self.past_winners, key=lambda w: w.timestamp, reverse=True)
            pages = MenuPages(source=BotwWinnerListSource(past_winners, self.winner_day), clear_reactions_after=True)
            await pages.start(ctx)
        else:
            await ctx.send('There have been no winners yet.')

    @biasoftheweek.command()
    @has_winner_role()
    async def icon(self, ctx):
        try:
            file = await ctx.message.attachments[0].read()
            await ctx.guild.edit(icon=file)
            await ctx.message.add_reaction(CHECK_EMOJI)
        except IndexError:
            raise commands.BadArgument('Icon missing.')
        await ctx.message.add_reaction(CHECK_EMOJI)

    @icon.error
    async def icon_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send('Only the current BotW winner may change the server icon.')
        elif isinstance(error, commands.BadArgument):
            await ctx.send('Attach the icon to your message.')
        else:
            await ctx.message.add_reaction(CROSS_EMOJI)
            logger.error(error)
