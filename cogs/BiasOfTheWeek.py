import asyncio
import logging
import random
from typing import List

import discord
import pendulum
from dateparser import parse
from discord.ext import commands, tasks
from discord.ext.menus import MenuPages

from const import CROSS_EMOJI
from menu import Confirm, BotwWinnerListSource
from models import BotwWinner, BotwState, Idol, Nomination
from util import ack, auto_help, BoolConverter

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(BiasOfTheWeek(bot))


def has_winner_role():
    async def predicate(ctx):
        query = """SELECT winner_changes
                   FROM botw_settings
                   WHERE guild = $1;"""
        winner_changes = await ctx.bot.pool.fetchval(query, ctx.guild.id)

        return winner_changes and ctx.bot.config['biasoftheweek']['winner_role_name'] in [role.name for role in
                                                                                          ctx.message.author.roles]

    return commands.check(predicate)


def botw_enabled():
    async def predicate(ctx):
        query = """SELECT enabled
                   FROM botw_settings
                   WHERE guild = $1;"""
        enabled = await ctx.bot.pool.fetchval(query, ctx.guild.id)
        return enabled

    return commands.check(predicate)


class BiasOfTheWeek(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.past_winners_collection = self.bot.config['biasoftheweek']['past_winners_collection']
        self.past_winners_time = int(self.bot.config['biasoftheweek']['past_winners_time'])
        self.winner_day = int(self.bot.config['biasoftheweek']['winner_day'])
        self.announcement_day = divmod((self.winner_day - 3), 7)[1]
        self._loop.start()

    async def _get_nominations(self, guild: discord.Guild) -> List[Nomination]:
        query = """SELECT *
                   FROM botw_nominations
                   WHERE guild = $1;"""

        rows = await self.bot.pool.fetch(query, guild.id)
        return [Nomination.from_record(row, self.bot) for row in rows]

    async def _get_winners(self, guild: discord.Guild) -> List[BotwWinner]:
        query = """SELECT *
                   FROM botw_winners
                   WHERE guild = $1;"""

        rows = await self.bot.pool.fetch(query, guild.id)
        return [BotwWinner.from_record(row, self.bot) for row in rows]

    async def _add_winner(self, guild: discord.Guild, date, idol: Idol, member: discord.Member):
        query = """INSERT INTO botw_winners (guild, date, idol_group, idol_name, member)
                   VALUES ($1, $2, $3, $4, $5);"""
        await self.bot.pool.execute(query, guild.id, date, idol.group, idol.name, member.id)

    async def _set_state(self, guild: discord.Guild, state: BotwState):
        query = """UPDATE botw_settings
                   SET state = $1
                   WHERE guild = $2;"""

        await self.bot.pool.execute(query, state.value, guild.id)

    async def _pick_winner(self, guild: discord.Guild, nominations: List[Nomination], silent=False):
        nomination = random.choice(nominations)
        pick = nomination.idol
        member = nomination.member

        query = """SELECT nominations_channel
                   FROM botw_settings
                   WHERE guild = $1;"""

        nominations_channel_id = await self.bot.pool.fetchval(query, guild.id)
        nominations_channel = self.bot.get_channel(nominations_channel_id)

        # Assign BotW winner role on next wednesday at 00:00 UTC
        now = pendulum.now('UTC')
        assign_date = now.next(self.winner_day)

        await nominations_channel.send(f'Bias of the Week ({now.week_of_year}-{now.year}): '
                                       f'{member if silent else member.mention}\'s pick **{pick}**. '
                                       f'You will be assigned the role '
                                       f'*{self.bot.config["biasoftheweek"]["winner_role_name"]}* on '
                                       f'{assign_date.to_cookie_string()}.')

        await self._add_winner(guild, now, pick, member)
        await self._clear_nominations(guild, member)

    async def _assign_winner_role(self, guild: discord.Guild, winner: BotwWinner):
        query = """SELECT *
                   FROM botw_settings
                   WHERE guild = $1;"""

        row = await self.bot.pool.fetchrow(query, guild.id)

        botw_channel = self.bot.get_channel(row['botw_channel'])
        nominations_channel = self.bot.get_channel(row['nominations_channel'])
        winner_changes = row['winner_changes']

        member = winner.member
        logger.info(f'Assigning winner role to {member} in {guild}')
        member = guild.get_member(member.id)
        botw_winner_role = discord.utils.get(guild.roles, name=self.bot.config['biasoftheweek']['winner_role_name'])
        await member.add_roles(botw_winner_role)
        await member.send(f'Hi, your pick **{winner.idol}** won this week\'s BotW. Congratulations!\n'
                          f'You may now post your pics and gfys in {botw_channel.mention}.')

        if winner_changes:
            await member.send(f'Don\'t forget to change the server name/icon using `.botw [name|icon]` '
                              f'in {nominations_channel.mention}.')

    async def _remove_winner_role(self, guild: discord.Guild, winner: BotwWinner):
        member = winner.member
        logger.info(f'Removing winner role from {member} in {guild}')
        member = guild.get_member(member.id)
        botw_winner_role = discord.utils.get(guild.roles, name=self.bot.config['biasoftheweek']['winner_role_name'])
        await member.remove_roles(botw_winner_role)

    async def _set_nomination(self, ctx, idol: Idol, old_idol: Idol = None):
        guild = ctx.guild
        member = ctx.author

        query = """INSERT INTO botw_nominations
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (guild, member) DO UPDATE
                   SET idol_group = $2, idol_name = $3;"""

        await self.bot.pool.execute(query, guild.id, idol.group, idol.name, member.id)

        await ctx.send(f'{ctx.author} nominates **{idol}** instead of **{old_idol}**.'
                       if old_idol else f'{ctx.author} nominates **{idol}**.')

    async def _clear_nominations(self, guild: discord.Guild, member: discord.Member = None):
        if member:
            query = """DELETE FROM botw_nominations
                       WHERE guild = $1 AND member = $2;"""

            await self.bot.pool.execute(query, guild.id, member.id)
        else:
            query = """DELETE FROM botw_nominations
                       WHERE guild = $1;"""

            await self.bot.pool.execute(query, guild.id)

    async def _disable(self, guild: int):
        query = """UPDATE botw_settings 
                   SET enabled = FALSE 
                   WHERE guild = $1;"""
        await self.bot.pool.execute(query, guild)

    async def cog_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return

        if isinstance(error, commands.CheckFailure):
            await ctx.send('BotW has not been enabled in this server.')
        else:
            logger.exception(error)

    @auto_help
    @commands.group(name='biasoftheweek', aliases=['botw'], brief='Organize Bias of the Week events',
                    invoke_without_command=True)
    @botw_enabled()
    async def biasoftheweek(self, ctx):
        await ctx.send_help(self.biasoftheweek)

    @biasoftheweek.command(brief='Sets up BotW in the server')
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx):
        def check(m):
            return m.channel == ctx.channel and m.author == ctx.author

        channel_converter = commands.TextChannelConverter()

        await ctx.send('Okay, let\'s set up Bias of the Week in this server. '
                       'Which channel do you want winners to post in? (Reply with a mention or an ID)')

        try:
            botw_channel = await self.bot.wait_for('message', check=check, timeout=60.0)
            botw_channel = await channel_converter.convert(ctx, botw_channel.content)

            await ctx.send('What channel should I send the winner announcement to? (Reply with a mention or an ID)')
            nominations_channel = await self.bot.wait_for('message', check=check, timeout=60.0)
            nominations_channel = await channel_converter.convert(ctx, nominations_channel.content)

            await ctx.send('Should winners be able to change the server icon and name? (yes/no)')
            botw_winner_changes = await self.bot.wait_for('message', check=check, timeout=60.0)
            botw_winner_changes = await BoolConverter().convert(ctx, botw_winner_changes.content)
        except asyncio.TimeoutError:
            await ctx.send(f'Timed out.\nPlease restart the setup using `{ctx.prefix}botw setup`.')
        except commands.CommandError as e:
            await ctx.send(f'{e}\nPlease restart the setup using `{ctx.prefix}botw setup`.')
        else:
            query = """INSERT INTO botw_settings
                       VALUES ($1, $2, $3, $4, $5, $6)
                       ON CONFLICT (guild) DO UPDATE
                       SET botw_channel = $1, 
                           enabled = $2, 
                           nominations_channel = $3,
                           winner_changes = $5;"""

            await self.bot.pool.execute(query, botw_channel.id, True, nominations_channel.id,
                                        BotwState.DEFAULT.value, botw_winner_changes, ctx.guild.id)

            # create role
            winner_role_name = self.bot.config['biasoftheweek']['winner_role_name']
            if role := discord.utils.get(ctx.guild.roles, name=winner_role_name):
                # botw role exists
                pass
            else:  # need to create botw role
                try:
                    role = await ctx.guild.create_role(name=winner_role_name, reason='BotW setup')
                except discord.Forbidden:
                    await ctx.send(f'Could not create role `{winner_role_name}`. Please create it yourself and'
                                   f' make sure it has send message permissions in {botw_channel.mention}.')

            if role:
                try:
                    await botw_channel.edit(overwrites={role: discord.PermissionOverwrite(send_messages=True)},
                                            reason='BotW setup')
                except discord.Forbidden:
                    pass

            await ctx.send(f'Bias of the Week is now enabled in this server! `{ctx.prefix}botw disable` to disable.')
            logger.info(f'BotW was set up in {ctx.guild}: %s, %s, %s',
                        botw_channel, nominations_channel, botw_winner_changes)

    @biasoftheweek.command(brief='Disable BotW in the server')
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx):
        await self._disable(ctx.guild.id)
        await ctx.send(f'Bias of the Week is now disabled in this server! `{ctx.prefix}botw setup` to re-enable it.')

    @biasoftheweek.command(brief='Nominates an idol')
    @botw_enabled()
    async def nominate(self, ctx, group: commands.clean_content, *, name: commands.clean_content):
        """
        Nominates an idol for next week's Bias of the Week.

        Example usage:
        `{prefix}botw nominate "Red Velvet" "Irene"`
        """
        idol = Idol(group, name)

        query = """SELECT "group", name 
                   FROM idols
                   ORDER BY SIMILARITY("group" || ' ' || name, $1) DESC
                   LIMIT 1;"""

        if row := await self.bot.pool.fetchrow(query, str(idol)):
            best_match = Idol.from_record(row)

            if not best_match == idol:
                confirm_match = await Confirm(f'**@{ctx.author}**, did you mean **{best_match}**?').prompt(ctx)
                if confirm_match:
                    idol = best_match

        query_dupe = """SELECT TRUE 
                        FROM botw_nominations 
                        WHERE guild = $1 AND idol_group = $2 AND idol_name = $3
                        LIMIT 1;"""

        query_past_win = """SELECT TRUE
                            FROM botw_winners
                            WHERE guild = $1 AND idol_group = $2 AND idol_name = $3
                                  AND date > $4
                            LIMIT 1;"""

        query_nomination = """SELECT *
                              FROM botw_nominations
                              WHERE guild = $1 AND member = $2;"""

        if await self.bot.pool.fetchval(query_dupe, ctx.guild.id, idol.group, idol.name):
            raise commands.BadArgument(f'**{idol}** has already been nominated. Please nominate someone else.')
        elif await self.bot.pool.fetchval(query_past_win, ctx.guild.id, idol.group, idol.name,
                                          pendulum.now().subtract(days=self.past_winners_time)):
            # check whether idol has won in the past
            raise commands.BadArgument(f'**{idol}** has already won in the past `{self.past_winners_time}` days. '
                                       f'Please nominate someone else.')
        elif row := await self.bot.pool.fetchrow(query_nomination, ctx.guild.id, ctx.author.id):
            old_idol = Idol(row['idol_group'], row['idol_name'])

            confirm_override = await Confirm(f'Your current nomination is **{old_idol}**. '
                                             f'Do you want to override it?').prompt(ctx)

            if confirm_override:
                await self._set_nomination(ctx, idol, old_idol)
        else:
            await self._set_nomination(ctx, idol)

    @biasoftheweek.command(brief='Clears a member\'s nomination')
    @botw_enabled()
    @commands.has_permissions(administrator=True)
    @ack
    async def clear(self, ctx, member: discord.Member = None):
        """
        Clears a member's nomination.
        Clears all of the guild's nominations if no member was specified.
        """
        if not member:
            confirm = await Confirm(f'**{ctx.author}**, do you really want to clear '
                                    f'this guild\'s nominations?').prompt(ctx)
            if confirm:
                await self._clear_nominations(ctx.guild)
        else:
            await self._clear_nominations(ctx.guild, member)

    @biasoftheweek.command(brief='Displays the current nominations')
    @botw_enabled()
    async def nominations(self, ctx):
        nominations = await self._get_nominations(ctx.guild)

        if nominations:
            embed = discord.Embed(title='Bias of the Week nominations')
            for nomination in nominations:
                embed.add_field(**nomination.to_field())

            await ctx.send(embed=embed)
        else:
            await ctx.send('So far, no idols have been nominated.')

    @biasoftheweek.command(brief='Manually picks a winner')
    @botw_enabled()
    @commands.has_permissions(administrator=True)
    async def winner(self, ctx, silent: bool = False):
        """
        Manually picks a winner.

        Do not use unless you know what you are doing! It will probably result in the picked winner getting skipped!
        """
        await self._pick_winner(ctx.guild, await self._get_nominations(ctx.guild), silent=silent)

    @biasoftheweek.command(brief='Skips next week\'s BotW draw')
    @botw_enabled()
    @commands.has_permissions(administrator=True)
    async def skip(self, ctx):
        query = """SELECT state
                   FROM botw_settings
                   WHERE guild = $1;"""
        state_val = await self.bot.pool.fetchval(query, ctx.guild.id)
        state = BotwState(state_val)

        if state == BotwState.WINNER_CHOSEN:
            raise commands.BadArgument('Can\'t skip because the current winner has not been notified yet.')

        await self._set_state(ctx.guild, BotwState.DEFAULT if state == BotwState.SKIP else BotwState.SKIP)

        next_announcement = pendulum.now('UTC').next(self.announcement_day)
        await ctx.send(f'BotW Winner selection on `{next_announcement.to_cookie_string()}` is '
                       f'now {"" if state == BotwState.DEFAULT else "**not** "}being skipped.')

    @biasoftheweek.command(brief='Displays past BotW winners')
    @botw_enabled()
    async def history(self, ctx):
        if len(past_winners := await self._get_winners(ctx.guild)) > 0:
            past_winners = sorted(past_winners, key=lambda w: w.date, reverse=True)
            pages = MenuPages(source=BotwWinnerListSource(past_winners, self.winner_day), clear_reactions_after=True)
            await pages.start(ctx)
        else:
            await ctx.send('So far there have been no winners.')

    @biasoftheweek.command(name='servername', aliases=['name'], brief='Changes the server name')
    @botw_enabled()
    @has_winner_role()
    @ack
    async def server_name(self, ctx, *, name):
        await ctx.guild.edit(name=name)

    @server_name.error
    async def server_name_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send('Only the current BotW winner may change the server name.')

    @biasoftheweek.command(brief='Changes the server icon')
    @botw_enabled()
    @has_winner_role()
    @ack
    async def icon(self, ctx):
        try:
            file = await ctx.message.attachments[0].read()
            await ctx.guild.edit(icon=file)
        except IndexError:
            raise commands.BadArgument('Icon missing.')

    @icon.error
    async def icon_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send('Only the current BotW winner may change the server icon.')
        elif isinstance(error, commands.BadArgument):
            await ctx.send('Attach the icon to your message.')
        else:
            await ctx.message.add_reaction(CROSS_EMOJI)
            logger.error(error)

    @biasoftheweek.command(brief='Manually adds a past BotW winner')
    @botw_enabled()
    @commands.has_permissions(administrator=True)
    @ack
    async def addwinner(self, ctx, member: discord.Member, starting_day, group, name):
        """
        Manually adds a past BotW winner.

        Example usage:
        `{prefix}botw addwinner @MemberX 2020-08-05 "Red Velvet" "Irene"`
        """
        day = parse(starting_day)
        day = pendulum.instance(day)

        prev_announcement_day = day.previous(self.announcement_day + 1)

        await self._add_winner(ctx.guild, prev_announcement_day, Idol(group, name), member)

    @biasoftheweek.command(name='load', brief='Parses a file containing idol names')
    @commands.is_owner()
    async def load_idols(self, ctx):
        try:
            idols_attachment = ctx.message.attachments[0]
        except IndexError:
            raise commands.BadArgument('Attach a file.')

        text = (await idols_attachment.read()).decode('UTF-8')
        lines = text.splitlines()
        lines_tokenized = [line.split('\t') for line in lines]

        with ctx.typing():
            query_delete = """DELETE FROM idols 
                              WHERE TRUE;"""
            await self.bot.pool.execute(query_delete)

            query_insert = """INSERT INTO idols ("group", name)
                              VALUES ($1, $2);"""
            await self.bot.pool.executemany(query_insert, lines_tokenized)

        await ctx.send(f'Successfully loaded `{len(lines)}` idols.')

    @biasoftheweek.command(brief='Displays the guild\'s BotW settings')
    @botw_enabled()
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        query = """SELECT *
                   FROM botw_settings
                   WHERE guild = $1;"""
        row = await self.bot.pool.fetchrow(query, ctx.guild.id)

        embed = discord.Embed(title=f'BotW settings of {ctx.guild}',
                              description=f'Use `{ctx.prefix}botw setup` to change these.') \
            .set_thumbnail(url=ctx.guild.icon_url) \
            .add_field(name='Enabled', value=row['enabled']) \
            .add_field(name='BotW channel', value=self.bot.get_channel(row['botw_channel']).mention) \
            .add_field(name='Winner announcement channel',
                       value=self.bot.get_channel(row['nominations_channel']).mention) \
            .add_field(name='State', value=BotwState(row['state']).value)

        await ctx.send(embed=embed)

    @biasoftheweek.command(brief='Sets the BotW state in the server')
    @commands.is_owner()
    async def state(self, ctx, state):
        state = BotwState(state)
        await self._set_state(ctx.guild, state)

    @tasks.loop(hours=1.0)
    async def _loop(self):
        # pendulum.set_test_now(pendulum.now('UTC').next(self.winner_day))
        logger.info('Hourly loop running')
        now = pendulum.now('UTC')

        query = """SELECT *
                   FROM botw_settings
                   WHERE enabled;"""

        # pick winner on announcement day
        if now.day_of_week == self.announcement_day and now.hour == 0:
            rows = await self.bot.pool.fetch(query)
            for guild_settings in rows:
                guild = self.bot.get_guild(guild_settings['guild'])

                if not guild:  # we're not in the guild anymore, disable botw
                    await self._disable(guild_settings['guild'])
                    continue

                nominations = await self._get_nominations(guild)
                state = BotwState(guild_settings['state'])

                if state not in (BotwState.SKIP, BotwState.WINNER_CHOSEN) and len(nominations) > 0:
                    await self._pick_winner(guild, nominations)
                    await self._set_state(guild, BotwState.WINNER_CHOSEN)
                else:
                    logger.info(f'Skipping BotW winner selection in {guild}')

        # assign role on winner day
        elif now.day_of_week == self.winner_day and now.hour == 0:
            rows = await self.bot.pool.fetch(query)
            for guild_settings in rows:
                guild = self.bot.get_guild(guild_settings['guild'])

                if not guild:  # we're not in the guild anymore, disable botw
                    await self._disable(guild_settings['guild'])
                    continue

                state = BotwState(guild_settings['state'])

                if state not in (BotwState.SKIP, BotwState.DEFAULT):
                    past_winners = await self._get_winners(guild)

                    if len(past_winners) >= 2:
                        winner, previous_winner = sorted(past_winners, key=lambda w: w.date,
                                                         reverse=True)[0:2]
                        await self._remove_winner_role(guild, previous_winner)
                    else:
                        winner = past_winners[0]

                    await self._assign_winner_role(guild, winner)
                else:
                    logger.info(f'Skipping BotW winner role assignment in {guild}')

                await self._set_state(guild, BotwState.DEFAULT)

    @_loop.before_loop
    async def loop_before(self):
        await self.bot.wait_until_ready()
