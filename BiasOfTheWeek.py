from discord.ext import commands
import discord
import random
import asyncio

CHECK_EMOTE = '✅'
CROSS_EMOTE = '❌'


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


class BiasOfTheWeek(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.nominations = {}

    @staticmethod
    def reaction_check(reaction, user, author, prompt_msg):
        return user == author and str(reaction.emoji) in [CHECK_EMOTE, CROSS_EMOTE] and \
               reaction.message.id == prompt_msg.id

    @commands.command()
    async def nominate(self, ctx, group: str, name: str):
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
                    await ctx.send(f'{ctx.author} nominates **{idol}** instead of **{old_idol}**.')
        else:
            self.nominations[ctx.author] = idol
            await ctx.send(f'{ctx.author} nominates **{idol}**.')

    @nominate.error
    async def nominate_error(self, ctx, error):
        if isinstance(error, commands.TooManyArguments):
            await ctx.send('Too many arguments! Please enclose the group idol name in quotes if they'
                           'consist of multiple words.')
        print(error)
        await ctx.send('Please use the following format: `.nominate GROUP IDOL`. '
                       '\nEnclose in quotation marks if either contains spaces.')

    @commands.command()
    async def nominations(self, ctx):
        embed = discord.Embed(title='Bias of the Week nominations')
        for key, value in self.nominations.items():
            embed.add_field(name=key, value=value)

        await ctx.send(embed=embed)

    @commands.command(name='pickwinner')
    async def pick_winner(self, ctx):
        member, pick = random.choice(list(self.nominations.items()))
        await ctx.send(f'Bias of the Week: {member.mention}\'s pick: **{pick}**')
