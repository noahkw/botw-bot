import logging
import random

import discord
import pendulum
from dateparser import parse
from discord.ext import commands, tasks
from discord.ext.menus import MenuPages

from cogs import AinitMixin, CustomCog
from const import CROSS_EMOJI
from menu import Confirm, BotwWinnerListSource, SelectionMenu, IdolListSource
from models import BotwWinner, BotwState
from models import Idol, Nomination
from util import ratio, ack, auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(BiasOfTheWeek(bot))


def has_winner_role():
    def predicate(ctx):
        return ctx.bot.config['biasoftheweek']['winner_role_name'] in [role.name for role in ctx.message.author.roles]

    return commands.check(predicate)


def match_idol(idol, collection, cutoff=75):
    matches = [(i, ratio(str(i).lower(), str(idol).lower())) for i in collection]
    best_match = max(matches, key=lambda i: i[1])

    return best_match[0] if best_match[1] > cutoff else None


class BiasOfTheWeek(CustomCog, AinitMixin):
    def __init__(self, bot):
        super().__init__(bot)
        self.nominations = {}  # maps guild.id -> user.id -> idol
        self.nominations_collection = self.bot.config['biasoftheweek']['nominations_collection']
        self.idols = set()
        self.idols_collection = self.bot.config['biasoftheweek']['idols_collection']
        self.past_winners = {}  # maps guild.id -> List[BotwWinner]
        self.past_winners_collection = self.bot.config['biasoftheweek']['past_winners_collection']
        self.past_winners_time = int(self.bot.config['biasoftheweek']['past_winners_time'])
        self.winner_day = int(self.bot.config['biasoftheweek']['winner_day'])
        self.announcement_day = divmod((self.winner_day - 3), 7)[1]

        super(AinitMixin).__init__()

    async def _ainit(self):
        _nominations = await self.bot.db.get(self.nominations_collection)

        for _nomination in _nominations:
            nomination = Nomination.from_dict(_nomination.to_dict(), self.bot, _nomination.id)
            member = nomination.member
            guild = nomination.guild
            self.get_nominations(guild)[member.id] = nomination

        logger.info(f'# Initial nominations from db: {len(self.nominations)}')

        _past_winners = await self.bot.db.get(self.past_winners_collection)

        for _past_winner in _past_winners:
            past_winner = BotwWinner.from_dict(_past_winner.to_dict(), self.bot)
            self.get_past_winners(past_winner.guild).append(past_winner)

        self.idols = set([Idol.from_dict(idol.to_dict()) for idol in await self.bot.db.get(self.idols_collection)])

        self._loop.start()

    def get_nominations(self, guild: discord.Guild):
        return self.nominations.setdefault(guild.id, {})

    def get_past_winners(self, guild: discord.Guild):
        return self.past_winners.setdefault(guild.id, [])

    async def set_nomination(self, ctx, idol: Idol, old_idol: Idol = None):
        guild = ctx.guild
        member = ctx.author

        # self.get_nominations(guild)[member.id] = idol

        if old_idol:  # update old db entry
            nomination = self.get_nominations(guild)[member.id]
            nomination.idol = idol
            await self.bot.db.update(self.nominations_collection, nomination.id, {'idol': idol.to_dict()})
            await ctx.send(f'{ctx.author} nominates **{idol}** instead of **{old_idol}**.')
        else:  # need to create new db entry
            nomination = Nomination(None, member, guild, idol)
            id_ = await self.bot.db.set_get_id(self.nominations_collection, nomination.to_dict())
            nomination.id = id_
            self.get_nominations(guild)[member.id] = nomination
            await ctx.send(f'{ctx.author} nominates **{idol}**.')

    @auto_help
    @commands.group(name='biasoftheweek', aliases=['botw'], brief='Organize Bias of the Week events')
    async def biasoftheweek(self, ctx):
        pass

    @biasoftheweek.command()
    async def nominate(self, ctx, group: commands.clean_content, name: commands.clean_content):
        idol = Idol(group, name)
        best_match = match_idol(idol,
                                [winner.idol for winner in self.get_past_winners(ctx.guild)] +
                                list(self.idols) +
                                list(self.nominations.values()))
        if best_match is not None and not best_match == idol:
            confirm_match = await Confirm(f'Did you mean **{best_match}**?').prompt(ctx)
            if confirm_match:
                idol = best_match

        if idol in [nomination.idol for nomination in self.get_nominations(ctx.guild).values()]:
            raise commands.BadArgument(f'**{idol}** has already been nominated. Please nominate someone else.')
        elif idol in [winner.idol for winner in self.get_past_winners(ctx.guild) if
                      winner.timestamp > pendulum.now().subtract(
                          days=self.past_winners_time)]:  # check whether idol has won in the past
            raise commands.BadArgument(f'**{idol}** has already won in the past `{self.past_winners_time}` days. '
                                       f'Please nominate someone else.')
        elif ctx.author.id in self.get_nominations(ctx.guild).keys():
            old_idol = self.get_nominations(ctx.guild)[ctx.author.id].idol

            confirm_override = await Confirm(f'Your current nomination is **{old_idol}**. '
                                             f'Do you want to override it?').prompt(ctx)

            if confirm_override:
                await self.set_nomination(ctx, idol, old_idol)
        else:
            await self.set_nomination(ctx, idol)

    async def _clear_nominations(self, guild: discord.Guild, member: discord.Member):
        nomination = self.get_nominations(guild).pop(member.id)
        await self.bot.db.delete(self.nominations_collection, document=nomination.id)

    @biasoftheweek.command(name='clearnomination')
    @commands.has_permissions(administrator=True)
    @ack
    async def clear_nomination(self, ctx, member: discord.Member):
        await self._clear_nominations(ctx.guild, member)

    @biasoftheweek.command()
    async def nominations(self, ctx):
        if len(nominations := self.get_nominations(ctx.guild).values()) > 0:
            embed = discord.Embed(title='Bias of the Week nominations')
            for nomination in nominations:
                embed.add_field(**nomination.to_field())

            await ctx.send(embed=embed)
        else:
            await ctx.send('So far, no idols have been nominated.')

    @biasoftheweek.command()
    @commands.has_permissions(administrator=True)
    async def winner(self, ctx, silent: bool = False):
        await self._pick_winner(ctx.guild, silent=silent)

    async def _pick_winner(self, guild: discord.Guild, silent=False):
        member, pick = random.choice(list(self.get_nominations(guild).items()))

        settings_cog = self.bot.get_cog('Settings')
        settings = await settings_cog.get_settings(guild)
        nominations_channel = settings.botw_nominations_channel.value

        # Assign BotW winner role on next wednesday at 00:00 UTC
        now = pendulum.now('UTC')
        assign_date = now.next(self.winner_day)

        await nominations_channel.send(
            f"""Bias of the Week ({now.week_of_year}-{now.year}): {member if silent else member.mention}\'s pick **{pick}**. 
You will be assigned the role *{self.bot.config['biasoftheweek']['winner_role_name']}* on {assign_date.to_cookie_string()}.""")

        botw_winner = BotwWinner(member, guild, pick, now)
        self.get_past_winners(guild).append(botw_winner)
        await self.bot.db.add(self.past_winners_collection, botw_winner.to_dict())
        await self._clear_nominations(guild, member)

    async def _assign_winner_role(self, guild: discord.Guild, winner: BotwWinner):
        settings_cog = self.bot.get_cog('Settings')
        settings = await settings_cog.get_settings(guild)
        botw_channel = settings.botw_channel.value
        nominations_channel = settings.botw_nominations_channel.value

        member = winner.member
        logger.info(f'Assigning winner role to {member} in {guild}')
        member = guild.get_member(member.id)
        botw_winner_role = discord.utils.get(guild.roles, name=self.bot.config['biasoftheweek']['winner_role_name'])
        await member.add_roles(botw_winner_role)
        await member.send(f'Hi, your pick **{winner.idol}** won this week\'s BotW. Congratulations!\n'
                          f'You may now post your pics and gfys in {botw_channel.mention}.\n'
                          f'Don\'t forget to change the server icon using `.botw icon`'
                          f' in {nominations_channel.mention}.')

    async def _remove_winner_role(self, guild: discord.Guild, winner: BotwWinner):
        member = winner.member
        logger.info(f'Removing winner role from {member} in {guild}')
        member = guild.get_member(member.id)
        botw_winner_role = discord.utils.get(guild.roles, name=self.bot.config['biasoftheweek']['winner_role_name'])
        await member.remove_roles(botw_winner_role)

    @biasoftheweek.command()
    @commands.is_owner()
    async def skip(self, ctx):
        settings_cog = self.bot.get_cog('Settings')
        settings = await settings_cog.get_settings(ctx.guild)
        state = settings.botw_state.value
        if state == BotwState.WINNER_CHOSEN:
            raise commands.BadArgument('Can\'t skip because the current winner has not been notified yet.')

        await settings_cog.update(ctx.guild, 'botw_state',
                                  BotwState.DEFAULT if state == BotwState.SKIP else BotwState.SKIP)

        next_announcement = pendulum.now('UTC').next(self.announcement_day)
        await ctx.send(f'BotW Winner selection on `{next_announcement.to_cookie_string()}` is '
                       f'now {"" if state == BotwState.DEFAULT else "not "}being skipped.')

    @tasks.loop(hours=1.0)
    async def _loop(self):
        # pendulum.set_test_now(pendulum.now('UTC').next(self.winner_day))
        logger.info('Hourly loop running')
        now = pendulum.now('UTC')

        settings_cog = self.bot.get_cog('Settings')

        for guild in self.bot.guilds:
            settings = await settings_cog.get_settings(guild)
            if not settings.botw_enabled:
                continue

            # pick winner on announcement day
            if now.day_of_week == self.announcement_day and now.hour == 0:
                if settings.botw_state.value not in (BotwState.SKIP, BotwState.WINNER_CHOSEN) and len(
                        self.get_nominations(guild)) > 0:
                    await self._pick_winner(guild)
                    await settings_cog.update(guild, 'botw_state', BotwState.WINNER_CHOSEN)
                else:
                    logger.info(f'Skipping BotW winner selection in {guild}')

            # assign role on winner day
            elif now.day_of_week == self.winner_day and now.hour == 0:
                if settings.botw_state.value not in (BotwState.SKIP, BotwState.DEFAULT):
                    winner, previous_winner = sorted(self.past_winners, key=lambda w: w.timestamp, reverse=True)[0:2]
                    await self._remove_winner_role(guild, previous_winner)
                    await self._assign_winner_role(guild, winner)
                else:
                    logger.info(f'Skipping BotW winner role assignment in {guild}')

                await settings_cog.update(guild, 'botw_state', BotwState.DEFAULT)

    @_loop.before_loop
    async def loop_before(self):
        await self.bot.wait_until_ready()

    @biasoftheweek.command()
    async def history(self, ctx):
        if len(past_winners := self.get_past_winners(ctx.guild)) > 0:
            past_winners = sorted(past_winners, key=lambda w: w.timestamp, reverse=True)
            pages = MenuPages(source=BotwWinnerListSource(past_winners, self.winner_day), clear_reactions_after=True)
            await pages.start(ctx)
        else:
            await ctx.send('So far there have been no winners.')

    @biasoftheweek.command(name='servername', aliases=['name'])
    @has_winner_role()
    @ack
    async def server_name(self, ctx, *, name):
        await ctx.guild.edit(name=name)

    @biasoftheweek.command()
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

    @biasoftheweek.command()
    @commands.has_permissions(administrator=True)
    @ack
    async def addwinner(self, ctx, member: discord.Member, starting_day, group, name):
        day = parse(starting_day)
        day = pendulum.instance(day)

        prev_announcement_day = day.previous(self.announcement_day + 1)

        botw_winner = BotwWinner(member, ctx.guild, Idol(group, name), prev_announcement_day)
        self.get_past_winners(ctx.guild).append(botw_winner)
        await self.bot.db.add(self.past_winners_collection, botw_winner.to_dict())

    @biasoftheweek.command(name='load')
    @commands.is_owner()
    async def load_idols(self, ctx):
        try:
            idols_attachment = ctx.message.attachments[0]
        except IndexError:
            raise commands.BadArgument('Attach a file.')

        text = (await idols_attachment.read()).decode('UTF-8')
        lines = text.splitlines()
        lines_tokenized = [line.split(' ') for line in lines]

        seen_groups = set()

        for tokens in lines_tokenized:
            sublists = [(' '.join(tokens[:i]), ' '.join(tokens[i:])) for i in range(1, len(tokens))]

            try:
                for candidate in sublists:
                    if (idol := Idol(*candidate)) in self.idols:
                        seen_groups.add(idol.group)
                        raise Exception()  # raise to exit outer loop
            except Exception:
                continue

            group_candidates = set(token[0] for token in sublists)

            if len(tokens) == 2:
                # easy case
                idol = Idol(*tokens)
                seen_groups.add(idol.group)

                self.idols.add(idol)
                await self.bot.db.add(self.idols_collection, idol.to_dict())
            elif group := group_candidates.intersection(seen_groups):
                group = group.pop()  # want a string, not a set
                name = [tokens[1] for tokens in sublists if tokens[0] == group].pop()
                idol = Idol(group, name)
                self.idols.add(idol)
                await self.bot.db.add(self.idols_collection, idol.to_dict())
            else:
                correct = await self.prompt_idol_correction(ctx, sublists)

                if correct is not None:
                    # filter
                    seen_groups.add(correct.group)
                    self.idols.add(correct)
                    await self.bot.db.add(self.idols_collection, correct.to_dict())

    async def prompt_idol_correction(self, ctx, sublists):
        pages = SelectionMenu(source=IdolListSource(sublists))
        selection = await pages.prompt(ctx)
        return Idol(selection[0], selection[1])
