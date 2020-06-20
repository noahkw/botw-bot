import asyncio
import logging
import random
import typing

from discord.ext import commands
from discord.ext.menus import MenuPages

from const import CHECK_EMOJI
from menu import Confirm, TagListSource, PseudoMenu, SelectionMenu
from models import Tag
from util import ordered_sublists, ratio

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Tags(bot))


class TagConverter(commands.Converter):
    async def convert(self, ctx, argument):
        cog = ctx.bot.get_cog('Tags')
        try:
            tag = [tag for tag in cog.tags if tag.id == argument].pop()
            return [tag]
        except IndexError:
            # argument was not an ID, search triggers
            tags = await cog.get_tags_by_trigger(argument)
            if len(tags) > 0:
                return tags
            else:
                raise commands.BadArgument(f'Tag {argument} could not be found.')


class BoolConverter(commands.Converter):
    async def convert(self, ctx, argument):
        lowered = argument.lower()
        if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
            return True
        elif lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
            return False
        else:
            raise commands.BadArgument(lowered + ' is not a recognized boolean option')


class Tags(commands.Cog):
    FORMATTED_KEYS = [f'`{key}`' for key in Tag.EDITABLE]

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

    async def get_tags_by_trigger(self, trigger, fuzzy=75):
        if not fuzzy:
            tags = [tag for tag in self.tags if tag.trigger.lower() == trigger.lower()]
        else:
            tags = [tag for tag in self.tags if ratio(tag.trigger.lower(), trigger.lower()) > fuzzy]
        return tags

    async def get_duplicates(self, trigger, reaction):
        return [tag for tag in self.tags if (tag.trigger == trigger and tag.reaction == reaction)]

    @commands.group(aliases=['tags'], invoke_without_command=True)
    async def tag(self, ctx, *, args=None):
        await ctx.invoke(self.list, dm=args)

    @tag.command()
    async def add(self, ctx, in_msg_trigger: typing.Optional[bool] = False, trigger: commands.clean_content = '', *,
                  reaction: commands.clean_content):
        tag = Tag(None, trigger, reaction, ctx.author, in_msg_trigger=in_msg_trigger)
        matches = await self.get_duplicates(trigger, reaction)
        if len(matches) > 0:
            raise commands.BadArgument(f'This tag already exists (`{matches[0].id}`).')
        else:
            id_ = await self.bot.db.set_get_id(self.tags_collection, tag.to_dict())
            tag.id = id_
            self.tags.append(tag)
            await ctx.message.add_reaction(CHECK_EMOJI)

    @tag.command(aliases=['remove'])
    async def delete(self, ctx, tag: TagConverter):
        if len(tag) == 1:
            selection = tag[0]
        else:
            pages = SelectionMenu(source=TagListSource(tag))
            selection = await pages.prompt(ctx)

        # only allow tag owner and admins to delete tags
        if selection.creator != ctx.author and not ctx.author.guild_permissions.administrator:
            raise commands.BadArgument('You\'re not this tag\'s owner.')
        else:
            confirm = await Confirm(f'Are you sure you want to delete the tag with ID {selection.id}, '
                                    f'trigger `{selection.trigger}` and reaction {selection.reaction}?').prompt(ctx)

            if confirm:
                self.tags.remove(selection)
                await self.bot.db.delete(self.tags_collection, selection.id)
                await ctx.send(f'Tag `{selection.id}` was deleted.')

    @tag.command(aliases=['change'])
    async def edit(self, ctx, tag: TagConverter, key, *, new_value: commands.clean_content):
        if len(tag) == 1:
            selection = tag[0]
        else:
            pages = SelectionMenu(source=TagListSource(tag))
            selection = await pages.prompt(ctx)

        # only allow tag owner and admins to edit tags
        if selection.creator != ctx.author and not ctx.author.guild_permissions.administrator:
            raise commands.BadArgument('You\'re not this tag\'s owner.')
        elif key not in Tag.EDITABLE:
            raise commands.BadArgument(f'Cannot edit `{key}`. Valid choices: {", ".join(self.FORMATTED_KEYS)}.')
        else:
            if key == 'in_msg_trigger':
                new_value = await BoolConverter().convert(ctx, new_value)
            elif key in ['trigger', 'reaction']:
                # check whether we are creating a duplicate
                matches = await self.get_duplicates(new_value if key == 'trigger' else selection.trigger,
                                                    new_value if key == 'reaction' else selection.reaction)
                if len(matches) > 0:
                    raise commands.BadArgument(f'This edit would create a duplicate of tag `{matches[0].id}`.')

            old_value = getattr(selection, key)
            setattr(selection, key, new_value)
            await self.bot.db.update(self.tags_collection, selection.id, {key: new_value})
            await ctx.send(f'Tag `{selection.id}` was edited. Old {key}:\n{old_value}')

    @tag.command()
    async def list(self, ctx, dm=False):
        """
        Sends a list of all tags in the server to the channel.
        .tag list true for the entire list via DM.
        """
        if len(self.tags) > 0:
            if dm:
                menu = PseudoMenu(TagListSource(self.tags, per_page=15), ctx.author)
                await menu.start()
            else:
                pages = MenuPages(source=TagListSource(self.tags), clear_reactions_after=True)
                await pages.start(ctx)
        else:
            await ctx.send('Try adding a few tags first!')

    @tag.command()
    async def info(self, ctx, *, tag: TagConverter):
        if len(tag) == 1:
            await ctx.send(embed=tag[0].info_embed())
        else:
            pages = SelectionMenu(source=TagListSource(tag))
            selection = await pages.prompt(ctx)
            await ctx.send(embed=selection.info_embed())

    @tag.command()
    async def random(self, ctx):
        if len(self.tags) < 1:
            await ctx.send('Try to add a few tags first!')
        else:
            await self.invoke_tag(ctx, random.choice(self.tags), info=True)

    @tag.command()
    async def search(self, ctx, *, tag: TagConverter):
        pages = MenuPages(source=TagListSource(tag), clear_reactions_after=True)
        await pages.start(ctx)

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
