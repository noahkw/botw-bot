import asyncio
import logging
import random

import discord
import pendulum
from discord.ext import commands

from cogs.Scheduler import Job
from const import CROSS_EMOJI, CHECK_EMOJI

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(BiasOfTheWeek(bot))


class Idol:
    def __init__(self, group, name):
        self.group = group
        self.name = name

    def __str__(self):
        return f'{self.group} {self.name}'

    def __eq__(self, other):
        if not isinstance(other, Idol):
            return NotImplemented
        return str.lower(self.group) == str.lower(other.group) and str.lower(
            self.name) == str.lower(other.name)

    def to_dict(self):
        return {'group': self.group, 'name': self.name}

    @staticmethod
    def from_dict(source):
        return Idol(source['group'], source['name'])


class BotwWinner:
    def __init__(self, member, idol, timestamp):
        self.member = member
        self.idol = idol
        self.timestamp = timestamp

    def __eq__(self, other):
        if not isinstance(other, BotwWinner):
            return NotImplemented
        return self.member == other.member and self.idol == other.idol and self.timestamp == other.timestamp

    def to_dict(self):
        return {
            'member': self.member.id,
            'idol': self.idol.to_dict(),
            'timestamp': self.timestamp
        }

    @staticmethod
    def from_dict(source, bot):
        return BotwWinner(bot.get_user(source['member']),
                          Idol.from_dict(source['idol']), source['timestamp'])


class BiasOfTheWeek(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.nominations = {}
        self.nominations_collection = self.bot.config['biasoftheweek'][
            'nominations_collection']
        self.past_winners_collection = self.bot.config['biasoftheweek'][
            'past_winners_collection']
        self.past_winners_time = self.bot.config['biasoftheweek'][
            'past_winners_time']

        if self.bot.loop.is_running():
            asyncio.create_task(self._ainit())
        else:
            self.bot.loop.run_until_complete(self._ainit())

    async def _ainit(self):
        _nominations = await self.bot.db.get(self.nominations_collection)

        for nomination in _nominations:
            self.nominations[self.bot.get_user(int(
                nomination.id))] = Idol.from_dict(nomination.to_dict())

        logger.info(f'Initial nominations from db: {self.nominations}')

        self.past_winners = [
            BotwWinner.from_dict(winner.to_dict(), self.bot)
            for winner in await self.bot.db.get(self.past_winners_collection)
        ]

    @staticmethod
    def reaction_check(reaction, user, author, prompt_msg):
        return user == author and str(reaction.emoji) in [CHECK_EMOJI, CROSS_EMOJI] and \
               reaction.message.id == prompt_msg.id

    @commands.group(name='biasoftheweek', aliases=['botw'])
    async def biasoftheweek(self, ctx):
        pass

    @biasoftheweek.command()
    async def nominate(self, ctx, group: commands.clean_content,
                       name: commands.clean_content):
        idol = Idol(group, name)

        if idol in self.nominations.values():
            await ctx.send(
                f'**{idol}** has already been nominated. Please nominate someone else.'
            )
        elif idol in [
                winner.idol for winner in self.past_winners
                if winner.timestamp > pendulum.now().subtract(
                    days=int(self.past_winners_time)).timestamp()
        ]:  # check whether idol has won in the past
            await ctx.send(
                f'**{idol}** has already won in the past `{self.past_winners_time}` days. Please nominate someone else.'
            )
        elif ctx.author in self.nominations.keys():
            old_idol = self.nominations[ctx.author]
            prompt_msg = await ctx.send(
                f'Your current nomination is **{old_idol}**. Do you want to override it?'
            )
            await prompt_msg.add_reaction(CHECK_EMOJI)
            await prompt_msg.add_reaction(CROSS_EMOJI)
            try:
                reaction, user = await self.bot.wait_for(
                    'reaction_add',
                    timeout=60.0,
                    check=lambda reaction, user: self.reaction_check(
                        reaction, user, ctx.author, prompt_msg))
            except asyncio.TimeoutError:
                pass
            else:
                await prompt_msg.delete()
                if reaction.emoji == CHECK_EMOJI:
                    self.nominations[ctx.author] = idol
                    await self.bot.db.set(self.nominations_collection,
                                          str(ctx.author.id), idol.to_dict())
                    await ctx.send(
                        f'{ctx.author} nominates **{idol}** instead of **{old_idol}**.'
                    )
        else:
            self.nominations[ctx.author] = idol
            await self.bot.db.set(self.nominations_collection,
                                  str(ctx.author.id), idol.to_dict())
            await ctx.send(f'{ctx.author} nominates **{idol}**.')

    @nominate.error
    async def nominate_error(self, ctx, error):
        await ctx.send(error)

    @biasoftheweek.command(name='clearnominations')
    @commands.has_permissions(administrator=True)
    async def clear_nominations(self, ctx, member: discord.Member = None):
        if member is None:
            self.nominations = {}
            await self.bot.db.delete(self.nominations_collection)
        else:
            self.nominations.pop(member)
            await self.bot.db.delete(self.nominations_collection,
                                     document=str(member.id))

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
    async def winner(self,
                     ctx,
                     silent: bool = False,
                     fast_assign: bool = False):
        member, pick = random.choice(list(self.nominations.items()))

        # Assign BotW winner role on next wednesday at 00:00 UTC
        now = pendulum.now('Europe/London')
        assign_date = now.add(
            seconds=120) if fast_assign else now.next(pendulum.WEDNESDAY)

        await ctx.send(
            f"""Bias of the Week ({now.week_of_year}-{now.year}): {member if silent else member.mention}\'s pick **{pick}**. 
You will be assigned the role *{self.bot.config['biasoftheweek']['winner_role_name']}* at {assign_date.to_cookie_string()}."""
        )

        botw_winner = BotwWinner(member, pick, now.timestamp())
        self.past_winners.append(botw_winner)
        await self.bot.db.add(self.past_winners_collection,
                              botw_winner.to_dict())

        scheduler = self.bot.get_cog('Scheduler')
        if scheduler is not None:
            await scheduler.add_job(
                Job('assign_winner_role', [ctx.guild.id, member.id],
                    assign_date.float_timestamp))

    @winner.error
    async def winner_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingPermissions):
            await ctx.send(error)
        logger.error(error)

    @biasoftheweek.command()
    async def history(self, ctx, number: int = 5):
        if len(self.past_winners) > 0:
            embed = discord.Embed(title='Past Bias of the Week winners')
            for past_winner in sorted(self.past_winners,
                                      key=lambda w: w.timestamp,
                                      reverse=True)[:number]:
                time = pendulum.from_timestamp(past_winner.timestamp)
                week = time.week_of_year
                year = time.year
                embed.add_field(
                    name=f'{year}-{week}',
                    value=f'{past_winner.idol} by {past_winner.member.mention}'
                )

            await ctx.send(embed=embed)
        else:
            await ctx.send('There have been no winners yet.')

    @biasoftheweek.command()
    async def icon(self, ctx):
        if self.bot.config['biasoftheweek']['winner_role_name'] in [
                role.name for role in ctx.message.author.roles
        ]:
            try:
                file = await ctx.message.attachments[0].read()
                await ctx.guild.edit(icon=file)
            except IndexError:
                await ctx.send('Attach the icon to your message.')
        else:
            await ctx.send(
                'Only the current BotW winner may change the server icon.')

    @icon.error
    async def icon_error(self, ctx, error):
        logger.error(error)
