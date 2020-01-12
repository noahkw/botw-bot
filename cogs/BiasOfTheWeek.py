import asyncio
import logging
import random

import discord
import pendulum
from discord.ext import commands

from cogs.Scheduler import Job

CHECK_EMOTE = '✅'
CROSS_EMOTE = '❌'

logger = logging.getLogger('discord')


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
        return str.lower(self.group) == str.lower(other.group) and str.lower(self.name) == str.lower(other.name)

    def to_dict(self):
        return {
            'group': self.group,
            'name': self.name
        }

    @staticmethod
    def from_dict(source):
        return Idol(source['group'], source['name'])


class BiasOfTheWeek(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.nominations = {}
        self.nominations_collection = self.bot.config['biasoftheweek']['nominations_collection']

        _nominations = self.bot.database.get(self.nominations_collection)
        for nomination in _nominations:
            self.nominations[self.bot.get_user(int(nomination.id))] = Idol.from_dict(nomination.to_dict())

        logger.info(f'Initial nominations from database: {self.nominations}')

    @staticmethod
    def reaction_check(reaction, user, author, prompt_msg):
        return user == author and str(reaction.emoji) in [CHECK_EMOTE, CROSS_EMOTE] and \
               reaction.message.id == prompt_msg.id

    @commands.command()
    async def nominate(self, ctx, group: commands.clean_content, name: commands.clean_content):
        idol = Idol(group, name)

        if idol in self.nominations.values():
            await ctx.send(f'**{idol}** has already been nominated. Please nominate someone else.')
        elif ctx.author in self.nominations.keys():
            old_idol = self.nominations[ctx.author]
            prompt_msg = await ctx.send(f'Your current nomination is **{old_idol}**. Do you want to override it?')
            await prompt_msg.add_reaction(CHECK_EMOTE)
            await prompt_msg.add_reaction(CROSS_EMOTE)
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0,
                                                         check=lambda reaction, user: self.reaction_check(reaction,
                                                                                                          user,
                                                                                                          ctx.author,
                                                                                                          prompt_msg))
            except asyncio.TimeoutError:
                pass
            else:
                await prompt_msg.delete()
                if reaction.emoji == CHECK_EMOTE:
                    self.nominations[ctx.author] = idol
                    self.bot.database.set(self.nominations_collection, str(ctx.author.id), idol.to_dict())
                    await ctx.send(f'{ctx.author} nominates **{idol}** instead of **{old_idol}**.')
        else:
            self.nominations[ctx.author] = idol
            self.bot.database.set(self.nominations_collection, str(ctx.author.id), idol.to_dict())
            await ctx.send(f'{ctx.author} nominates **{idol}**.')

    @nominate.error
    async def nominate_error(self, ctx, error):
        await ctx.send(error)

    @commands.command(name='clearnominations')
    @commands.has_permissions(administrator=True)
    async def clear_nominations(self, ctx):
        self.nominations = {}
        self.bot.database.delete(self.nominations_collection)
        await ctx.message.add_reaction(CHECK_EMOTE)

    @commands.command()
    async def nominations(self, ctx):
        if len(self.nominations) > 0:
            embed = discord.Embed(title='Bias of the Week nominations')
            for key, value in self.nominations.items():
                embed.add_field(name=key, value=value)

            await ctx.send(embed=embed)
        else:
            await ctx.send('So far, no idols have been nominated.')

    @commands.command(name='pickwinner')
    @commands.has_permissions(administrator=True)
    async def pick_winner(self, ctx, silent: bool = False, fast_assign: bool = False):
        member, pick = random.choice(list(self.nominations.items()))

        # Assign BotW winner role on next wednesday at 00:00 UTC
        now = pendulum.now('Europe/London')
        assign_date = now.add(seconds=120) if fast_assign else now.next(
            pendulum.WEDNESDAY)

        await ctx.send(
            f"""Bias of the Week ({now.week_of_year}-{now.year}): {member if silent else member.mention}\'s pick **{pick}**. 
You will be assigned the role *{self.bot.config['biasoftheweek']['winner_role_name']}* at {assign_date.to_cookie_string()}.""")

        scheduler = self.bot.get_cog('Scheduler')
        if scheduler is not None:
            await scheduler.add_job(Job('assign_winner_role', [ctx.guild.id, member.id], assign_date.float_timestamp))

    @pick_winner.error
    async def pick_winner_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingPermissions):
            await ctx.send(error)
        logger.error(error)
