import asyncio
import logging
import random
import typing

import discord
from discord.ext import commands
from discord.ext.menus import MenuPages

from const import CHECK_EMOJI
from menu import Confirm, TagListSource, PseudoMenu
from models import Tag
from util import ordered_sublists, ratio

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Tags(bot))


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tags_collection = self.bot.config['tags']['tags_collection']

        if self.bot.loop.is_running():
            asyncio.create_task(self._ainit())
        else:
            self.bot.loop.run_until_complete(self._ainit())

    async def _ainit(self):
        self.tags = [Tag.from_dict(tag.to_dict(), self.bot, tag.id) for tag in
                     await self.bot.db.get(self.tags_collection)]

        logger.info(f'Initial tags from db: {self.tags}')

    async def get_tags_by_trigger(self, trigger, fuzzy=None):
        if not fuzzy:
            tags = [tag for tag in self.tags if tag.trigger.lower() == trigger.lower()]
        else:
            tags = [tag for tag in self.tags if ratio(tag.trigger.lower(), trigger.lower()) > fuzzy]
        return tags

    @commands.group(aliases=['tags'])
    async def tag(self, ctx):
        pass

    @tag.command()
    async def add(self, ctx, in_msg_trigger: typing.Optional[bool] = False, trigger: commands.clean_content = '', *,
                  reaction: commands.clean_content):
        tag = Tag(None, trigger, reaction, ctx.author, in_msg_trigger=in_msg_trigger)
        if tag in self.tags:
            raise discord.InvalidArgument('This tag exists already.')
        else:
            id_ = await self.bot.db.set_get_id(self.tags_collection, tag.to_dict())
            tag.id = id_
            self.tags.append(tag)
            await ctx.message.add_reaction(CHECK_EMOJI)

    @add.error
    async def add_error(self, ctx, error):
        await ctx.send(error.original.args[0])

    @tag.command(aliases=['remove'])
    async def delete(self, ctx, id_):
        try:
            tag = [tag for tag in self.tags if tag.id == id_].pop()
            # only allow tag owner and admins to delete tags
            if tag.creator != ctx.author and not ctx.author.guild_permissions.administrator:
                await ctx.send('You can only remove tags that you added.')
            else:
                confirm = await Confirm(f'Are you sure you want to delete the tag with ID {tag.id}, '
                                        f'trigger `{tag.trigger}` and reaction {tag.reaction}?').prompt(ctx)

                if confirm:
                    self.tags.remove(tag)
                    await self.bot.db.delete(self.tags_collection, tag.id)
                    await ctx.send(f'Tag `{tag.id}` was deleted.')
        except IndexError:
            await ctx.send(f'No tag with ID `{id_}` was found.')

    @tag.command(aliases=['change'])
    async def edit(self, ctx, id_, new_reaction: commands.clean_content):
        try:
            tag = [tag for tag in self.tags if tag.id == id_].pop()
            # only allow tag owner and admins to edit tags
            if tag.creator != ctx.author and not ctx.author.guild_permissions.administrator:
                await ctx.send('You can only edit tags that you added.')
            else:
                old_reaction = tag.reaction
                tag.reaction = new_reaction
                await self.bot.db.update(self.tags_collection, tag.id, {'reaction': tag.reaction})
                await ctx.send(f'Tag `{tag.id}` was edited. Old reaction:\n{old_reaction}')
        except IndexError:
            await ctx.send(f'No tag with ID `{id_}` was found.')

    @tag.command()
    async def list(self, ctx, dm=False):
        """
        Sends a list of all tags in the server to the channel.
        .tag list true for the entire list via DM.
        """
        if len(self.tags) > 0:
            if dm:
                menu = PseudoMenu(TagListSource(self.tags), ctx.author)
                await menu.start()
            else:
                pages = MenuPages(source=TagListSource(self.tags), clear_reactions_after=True)
                await pages.start(ctx)
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
            await self.invoke_tag(ctx, random.choice(self.tags), info=True)

    @tag.command()
    async def search(self, ctx, *, trigger):
        matches = await self.get_tags_by_trigger(trigger, fuzzy=75)
        if len(matches) > 0:
            pages = MenuPages(source=TagListSource(matches), clear_reactions_after=True)
            await pages.start(ctx)
        else:
            await ctx.send('0 matches.')

    @commands.Cog.listener('on_message')
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

        # no arg defaults to splitting on whitespace
        tokens = message.content.lower().split()
        found_tags = []
        for tag in self.tags:
            if tag.trigger.lower() == message.content.lower():
                found_tags.append(tag)
            elif tag.in_msg_trigger:
                tag_tokens = tag.trigger.lower().split()
                sublists = ordered_sublists(tokens, len(tag_tokens))
                if tag_tokens in sublists:
                    found_tags.append(tag)

        if len(found_tags) >= 1:
            chosen_tag = random.choice(found_tags)
            await self.invoke_tag(message.channel, chosen_tag)

    async def invoke_tag(self, channel, tag, info=False):
        tag.use_count += 1
        await self.bot.db.update(self.tags_collection, tag.id, {'use_count': tag.use_count})
        if info:
            await channel.send(f'**{tag.trigger}** (*{tag.id}*) by {tag.creator}\n{tag.reaction}')
        else:
            await channel.send(tag.reaction)
