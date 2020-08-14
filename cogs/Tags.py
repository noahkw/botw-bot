import asyncio
import logging
import random
import typing

import discord
import pendulum
from discord.ext import commands
from discord.ext.menus import MenuPages

from cogs import CustomCog, AinitMixin
from menu import Confirm, TagListSource, PseudoMenu, SelectionMenu, DetailTagListSource
from models import Tag
from util import ordered_sublists, ratio, ack, auto_help
from util.converters import ReactionConverter, BoolConverter

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Tags(bot))


def guild_has_tags():
    async def predicate(ctx):
        cog = ctx.bot.get_cog('Tags')
        guild_tags = cog._get_tags(ctx.guild)

        return len(guild_tags) > 0

    return commands.check(predicate)


class TagConverter(commands.Converter):
    async def convert(self, ctx, argument):
        cog = ctx.bot.get_cog('Tags')
        try:
            tag = [tag for tag in cog._get_tags(ctx.guild) if tag.id == int(argument)].pop()
            return [tag]
        except (IndexError, ValueError):  # either argument is not an ID or it wasn't found
            # argument was not an ID, search triggers
            tags = await cog._get_tags_by_trigger(argument, ctx.guild)
            if len(tags) > 0:
                return tags
            else:
                raise commands.BadArgument(f'Tag {argument} could not be found.')


class Tags(CustomCog, AinitMixin):
    FORMATTED_KEYS = [f'`{key}`' for key in Tag.EDITABLE]
    ADD_SOME_TAGS = 'Try to add a few tags first.'

    def __init__(self, bot):
        super().__init__(bot)
        self.tags = {}

        super(AinitMixin).__init__()

    async def _ainit(self):
        await self.bot.wait_until_ready()

        query = """SELECT *
                   FROM tags;"""
        _tags = await self.bot.pool.fetch(query)

        for _tag in _tags:
            tag = Tag.from_record(_tag, self.bot)
            if tag.guild:  # ignore guilds that the bot is not in
                self._get_tags(tag.guild).append(tag)

        logger.info(f'# Initial tags from db: {sum([len(guild_tags) for guild_tags in self.tags.values()])}')

    async def _get_tags_by_trigger(self, trigger, guild, fuzzy=75):
        if not fuzzy:
            tags = [tag for tag in self._get_tags(guild) if tag.trigger.lower() == trigger.lower()]
        else:
            tags = [tag for tag in self._get_tags(guild) if ratio(tag.trigger.lower(), trigger.lower()) > fuzzy]
        return tags

    async def _get_duplicates(self, trigger, reaction, guild):
        return [tag for tag in self._get_tags(guild) if
                (tag.trigger == trigger and tag.reaction == reaction and tag.guild == guild)]

    def _get_tags(self, guild: discord.Guild):
        return self.tags.setdefault(guild.id, [])

    async def _invoke_tag(self, channel, tag, info=False):
        if info:
            await channel.send(f'**{tag.trigger}** (`{tag.id}`) by {tag.creator}\n{tag.reaction}')
        else:
            await channel.send(tag.reaction)

        tag.increment_use_count()

        query = """UPDATE tags
                   SET use_count = use_count + 1
                   WHERE id = $1;"""
        await self.bot.pool.execute(query, tag.id)

    @auto_help
    @commands.group(name='tags', aliases=['tag'], invoke_without_command=True, brief='Manage custom reactions')
    async def tag(self, ctx, *, args=None):
        await ctx.invoke(self.list, dm=args)

    @tag.command(aliases=['new', 'create'], brief='Adds a new tag')
    @ack
    async def add(self, ctx, in_msg: typing.Optional[bool] = False, trigger: commands.clean_content = '', *,
                  reaction: ReactionConverter):
        """
        Adds a new tag.

        Example usage:
        `{prefix}tag add wave https://gfycat.com/BenvolentCurteousGermanpinsher`

        Attach picture to the message and type:
        `{prefix}tag add "doggo pic"`

        To scan the entire message for the trigger **haha**:
        `{prefix}tag add true haha stop laughing`
        """
        matches = await self._get_duplicates(trigger, reaction, ctx.guild)

        if len(matches) > 0:
            raise commands.BadArgument(f'This tag already exists (`{matches[0].id}`).')
        else:
            query = """INSERT INTO tags (date, creator, guild, in_msg, reaction, trigger, use_count)
                       VALUES ($1, $2, $3, $4, $5, $6, 0)
                       RETURNING id;"""
            values = (pendulum.now('UTC'), ctx.author.id, ctx.guild.id, in_msg, reaction, trigger)
            id_ = await self.bot.pool.fetchval(query, *values)

            self._get_tags(ctx.guild).append(Tag(self.bot, id_, *values, 0))

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
                query = """DELETE FROM tags
                           WHERE id = $1;"""
                await self.bot.pool.execute(query, selection.id)

                self._get_tags(ctx.guild).remove(selection)

                await ctx.send(f'Tag `{selection.id}` was deleted.')

    @tag.command(aliases=['change'])
    async def edit(self, ctx, tag: TagConverter, key, *, value: commands.clean_content):
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
            if key == 'in_msg':
                value = await BoolConverter().convert(ctx, value)
            elif key in ['trigger', 'reaction']:
                # check whether we are creating a duplicate
                matches = await self._get_duplicates(value if key == 'trigger' else selection.trigger,
                                                     value if key == 'reaction' else selection.reaction, ctx.guild)
                if len(matches) > 0:
                    raise commands.BadArgument(f'This edit would create a duplicate of tag `{matches[0].id}`.')

            old_value = getattr(selection, key)
            setattr(selection, key, value)

            query = f"""UPDATE tags
                        SET {key} = $1
                        WHERE id = $2;"""
            await self.bot.pool.execute(query, value, selection.id)

            await ctx.send(f'Tag `{selection.id}` was edited. Old {key}:\n{old_value}')

    @guild_has_tags()
    @auto_help
    @tag.group(brief='Sends a list of all tags in the server', invoke_without_command=True)
    async def list(self, ctx):
        """
        Sends a list of all tags in the server.
        """
        pages = MenuPages(source=TagListSource(self._get_tags(ctx.guild)), clear_reactions_after=True)
        await pages.start(ctx)

    @list.command(name='detail', brief='Sends a detailed list')
    async def list_detail(self, ctx):
        """
        Sends a detailed list of all tags in the server.
        """
        pages = MenuPages(source=DetailTagListSource(self._get_tags(ctx.guild)), clear_reactions_after=True)
        await pages.start(ctx)

    @list.command(name='dm', brief='Sends the list via DM')
    async def list_dm(self, ctx):
        """
        Sends a list of all tags in the server via DM.
        """
        menu = PseudoMenu(TagListSource(self._get_tags(ctx.guild), per_page=15), ctx.author)
        await menu.start()

    @tag.command()
    async def info(self, ctx, *, tag: TagConverter):
        if len(tag) == 1:
            await ctx.send(embed=tag[0].info_embed())
        else:
            pages = SelectionMenu(source=TagListSource(tag))
            selection = await pages.prompt(ctx)
            await ctx.send(embed=selection.info_embed())

    @guild_has_tags()
    @tag.command()
    async def random(self, ctx):
        await self._invoke_tag(ctx, random.choice(self._get_tags(ctx.guild)), info=True)

    @tag.command()
    async def search(self, ctx, *, tag: TagConverter):
        pages = MenuPages(source=TagListSource(tag), clear_reactions_after=True)
        await pages.start(ctx)

    @list.error
    @random.error
    async def guild_has_no_tags_error(self, ctx, error):
        print(error)
        print(self.ADD_SOME_TAGS)

    @commands.Cog.listener('on_message')
    async def on_message(self, message):
        """Scan messages for tags to execute. As of now, the runtime is at worst O(words_in_message * number_tags),
        which scales poorly. Probably need to implement a more efficient matching algorithm down the line.

        If multiple tags are found in one message, it chooses one at random."""
        if message.author.bot or not message.guild:
            return

        ctx = await self.bot.get_context(message)
        # check if the message invoked is a command. mainly to stop tags from triggering on creation.
        if ctx.valid:
            return

        # no arg defaults to splitting on whitespace
        tokens = message.content.lower().split()
        found_tags = []
        for tag in self._get_tags(ctx.guild):
            if tag.trigger.lower() == message.content.lower():
                found_tags.append(tag)
            elif tag.in_msg:
                tag_tokens = tag.trigger.lower().split()
                sublists = ordered_sublists(tokens, len(tag_tokens))
                if tag_tokens in sublists:
                    found_tags.append(tag)

        if len(found_tags) >= 1:
            chosen_tag = random.choice(found_tags)
            await self._invoke_tag(message.channel, chosen_tag)
