import logging
import time
import random
import asyncio
import typing
import pendulum

import discord
from discord.ext import commands
from util import chunker
from const import CHECK_EMOJI, CROSS_EMOJI

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Tags(bot))


class Tag:
    SPLIT_EMBED_AFTER = 15

    def __init__(self,
                 id_,
                 trigger,
                 reaction,
                 creator,
                 in_msg_trigger=False,
                 use_count=0,
                 creation_date=None):
        self.id = id_
        self.trigger = trigger
        self.reaction = reaction
        self.creator = creator
        self.in_msg_trigger = in_msg_trigger
        self.use_count = use_count
        self.creation_date = time.time(
        ) if creation_date is None else creation_date

    def __str__(self):
        return f'({self.id}) {self.trigger} -> {self.reaction} (creator: {self.creator})'

    def to_list_element(self):
        return f'`{self.id}`: *{self.trigger}* by {self.creator}'

    def __eq__(self, other):
        if not isinstance(other, Tag):
            return NotImplemented
        return str.lower(self.trigger) == str.lower(
            other.trigger) and str.lower(self.reaction) == str.lower(
                other.reaction)

    def to_dict(self):
        return {
            'trigger': self.trigger,
            'reaction': self.reaction,
            'creator': self.creator.id,
            'in_msg_trigger': self.in_msg_trigger,
            'use_count': self.use_count,
            'creation_date': self.creation_date
        }

    def info_embed(self):
        embed = discord.Embed(title=f'Tag `{self.id}`')
        embed.add_field(name='Trigger', value=self.trigger)
        embed.add_field(name='Reaction', value=self.reaction)
        embed.add_field(name='Creator', value=self.creator.mention)
        embed.add_field(name='Triggers in message',
                        value=str(self.in_msg_trigger))
        embed.add_field(name='Use Count', value=str(self.use_count))
        embed.set_footer(
            text=
            f'Created on {pendulum.from_timestamp(self.creation_date).to_formatted_date_string()}'
        )
        return embed

    @staticmethod
    def from_dict(source, bot, id=None):
        return Tag(id,
                   source['trigger'],
                   source['reaction'],
                   bot.get_user(source['creator']),
                   in_msg_trigger=source['in_msg_trigger'],
                   use_count=source['use_count'],
                   creation_date=source['creation_date'])


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_listener(self.on_message, 'on_message')
        self.tags_collection = self.bot.config['tags']['tags_collection']

        if self.bot.loop.is_running():
            asyncio.create_task(self._ainit())
        else:
            self.bot.loop.run_until_complete(self._ainit())

    async def _ainit(self):
        self.tags = [
            Tag.from_dict(tag.to_dict(), self.bot, tag.id)
            for tag in await self.bot.db.get(self.tags_collection)
        ]

        logger.info(f'Initial tags from db: {self.tags}')

    @commands.group()
    async def tag(self, ctx):
        pass

    @tag.command()
    async def add(self,
                  ctx,
                  in_msg_trigger: typing.Optional[bool] = False,
                  trigger: commands.clean_content = '',
                  *,
                  reaction: commands.clean_content):
        tag = Tag(None,
                  trigger,
                  reaction,
                  ctx.author,
                  in_msg_trigger=in_msg_trigger)
        if tag in self.tags:
            raise discord.InvalidArgument('This tag exists already.')
        else:
            id_ = await self.bot.db.set_get_id(self.tags_collection,
                                               tag.to_dict())
            tag.id = id_
            self.tags.append(tag)
            await ctx.message.add_reaction(CHECK_EMOJI)

    @add.error
    async def add_error(self, ctx, error):
        await ctx.send(error.original.args[0])

    @staticmethod
    def reaction_check(reaction, user, author, prompt_msg):
        return user == author and str(reaction.emoji) in [CHECK_EMOJI, CROSS_EMOJI] and \
               reaction.message.id == prompt_msg.id

    @tag.command(aliases=['remove'])
    async def delete(self, ctx, id_):
        try:
            tag = [tag for tag in self.tags if tag.id == id_].pop()
            # allow deletion of tags only for owners and admins
            if tag.creator != ctx.author and not ctx.author.guild_permissions.administrator:
                await ctx.send('You can only remove tags that you added.')
            else:
                prompt_msg = await ctx.send(
                    f'Are you sure you want to delete the tag with ID {tag.id}, '
                    f'trigger `{tag.trigger}` and reaction {tag.reaction}?')
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
                        self.tags.remove(tag)
                        await self.bot.db.delete(self.tags_collection, tag.id)
                        await ctx.send(f'Tag `{tag.id}` was deleted.')
        except IndexError:
            await ctx.send(f'No tag with ID `{id_}` was found.')

    @tag.command()
    async def list(self, ctx):
        if len(self.tags) > 0:
            for i, tag_chunk in chunker(self.tags,
                                        Tag.SPLIT_EMBED_AFTER,
                                        return_index=True):
                embed = discord.Embed(title='Tags')
                embed.add_field(name=f'Reaction {i + 1}+',
                                value='\n'.join([
                                    Tag.to_list_element(tag)
                                    for tag in tag_chunk
                                ]))
                await ctx.send(embed=embed)
        else:
            await ctx.send('Try adding a few tags first!')

    @tag.command()
    async def info(self, ctx, id_):
        try:
            tag = [tag for tag in self.tags if tag.id == id_].pop()
            await ctx.send(embed=tag.info_embed())
        except IndexError:
            await ctx.send(f'No tag with ID `{id_}` was found.')

    @tag.command()
    async def random(self, ctx):
        if len(self.tags) < 1:
            await ctx.send('Try adding a few tags first!')
        else:
            await self.invoke_tag(ctx, random.choice(self.tags))

    async def on_message(self, message):
        """Scan messages for tags to execute. As of now, the runtime is at worst O(words_in_message * number_tags),
        which scales poorly. Probably need to implement a more efficient matching algorithm down the line.

        If multiple tags are found in one message, it chooses one at random."""
        if message.author.bot:
            return

        ctx = await self.bot.get_context(message)
        # check if the message invoked is a command. mainly to stop tags from triggering on creation.
        if ctx.valid:
            return

        found_tags = []
        for tag in self.tags:
            tokens = message.content.lower().split(' ')
            if tag.trigger.lower() == message.content.lower() or (
                    tag.in_msg_trigger and tag.trigger.lower() in tokens):
                found_tags.append(tag)

        if len(found_tags) >= 1:
            chosen_tag = random.choice(found_tags)
            await self.invoke_tag(message.channel, chosen_tag)

    async def invoke_tag(self, channel, tag):
        tag.use_count += 1
        await self.bot.db.update(self.tags_collection, tag.id,
                                 {'use_count': tag.use_count})
        await channel.send(tag.reaction)
