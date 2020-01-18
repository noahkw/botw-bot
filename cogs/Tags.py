import logging
import time

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Tags(bot))


class Tag:
    def __init__(self, trigger, reaction, creator, in_msg_trigger=False, use_count=0, creation_date=None):
        self.trigger = trigger
        self.reaction = reaction
        self.creator = creator
        self.in_msg_trigger = in_msg_trigger
        self.use_count = use_count
        self.creation_date = time.time() if creation_date is None else creation_date

    def __str__(self):
        return f'{self.trigger} -> {self.reaction} (creator: {self.creator})'

    def __eq__(self, other):
        if not isinstance(other, Tag):
            return NotImplemented
        return str.lower(self.trigger) == str.lower(other.trigger)

    def to_dict(self):
        return {
            'trigger': self.trigger,
            'reaction': self.reaction,
            'creator': self.creator.id,
            'in_msg_trigger': self.in_msg_trigger,
            'use_count': self.use_count,
            'creation_date': self.creation_date
        }

    @staticmethod
    def from_dict(source, bot):
        return Tag(source['trigger'], source['reaction'], bot.get_user(source['creator']),
                   in_msg_trigger=source['in_msg_trigger'], use_count=source['use_count'],
                   creation_date=source['creation_date'])


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_listener(self.on_message, 'on_message')
        self.tags_collection = self.bot.config['tags']['tags_collection']
        self.tags = [Tag.from_dict(tag.to_dict(), self.bot) for tag in self.bot.database.get(self.tags_collection)]

        logger.info(f'Initial tags from database: {self.tags}')

    @commands.group()
    async def tag(self, ctx):
        pass

    @tag.command()
    async def add(self, ctx, trigger: commands.clean_content, reaction: commands.clean_content,
                  in_msg_trigger: bool = False):
        if trigger in [tag.trigger for tag in self.tags]:
            raise discord.InvalidArgument('This command exists already.')
        else:
            tag = Tag(trigger, reaction, ctx.author, in_msg_trigger=in_msg_trigger)
            self.tags.append(tag)
            self.bot.database.add(self.tags_collection, tag.to_dict())

    @add.error
    async def add_error(self, ctx, error):
        await ctx.send(error.original.args[0])

    async def on_message(self, message):
        """Scan messages for tags to execute. As of now, the runtime is at worst O(words_in_message * number_tags),
        which scales poorly. Probably need to implement a more efficient matching algorithm down the line.

        If multiple tags are found in one message, it currently chooses the tag that was added last."""
        if message.author.bot:
            return

        ctx = await self.bot.get_context(message)
        # check if the message invoked a command. mainly to stop tags from triggering on creation.
        if ctx.valid:
            return

        for tag in self.tags:
            if message.content.startswith(tag.trigger) or (tag.in_msg_trigger and tag.trigger in message.content):
                await message.channel.send(tag.reaction)
                return
