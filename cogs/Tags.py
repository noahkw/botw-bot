import logging
import random
import typing

import discord
from discord.ext import commands
from discord.ext.menus import MenuPages

import db
from cogs import CustomCog, AinitMixin
from menu import Confirm, TagListSource, SelectionMenu, DetailTagListSource
from models import Tag
from util import ordered_sublists, ratio, auto_help, BoolConverter

logger = logging.getLogger(__name__)


async def setup(bot):
    await bot.add_cog(Tags(bot))


def guild_has_tags():
    async def predicate(ctx):
        cog = ctx.bot.get_cog("Tags")
        guild_tags = cog._get_tags(ctx.guild)

        return len(guild_tags) > 0

    return commands.check(predicate)


class TagConverter(commands.Converter):
    def __init__(self, prompt_selection=True):
        """
        :param prompt_selection: Whether to prompt the user to select exactly one tag.
        """
        self.prompt = prompt_selection

    async def convert(self, ctx, argument) -> typing.Union[Tag, typing.List[Tag]]:
        """
        :return: A single tag if self.prompt, a list of tags whose triggers match otherwise
        :raises commands.BadArgument: if no matching tag was found
        """

        cog = ctx.bot.get_cog("Tags")
        try:
            tag = [
                tag for tag in cog._get_tags(ctx.guild) if tag.tag_id == int(argument)
            ].pop()
            return tag
        except (
            IndexError,
            ValueError,
        ):  # either argument is not an ID or it wasn't found
            # argument was not an ID, search triggers
            tags = await cog._get_tags_by_trigger(argument, ctx.guild)

            if len(tags) == 1:
                return tags.pop()
            elif len(tags) > 0 and self.prompt:
                await ctx.send(
                    "Choose a tag by reacting with the corresponding number.",
                    delete_after=10,
                )
                pages = SelectionMenu(source=TagListSource(tags))
                selection = await pages.prompt(ctx)
                return selection
            elif len(tags) > 0:
                return tags
            else:
                raise commands.BadArgument(f"Tag {argument} could not be found.")


class Tags(CustomCog, AinitMixin):
    FORMATTED_KEYS = [f"`{key}`" for key in Tag.EDITABLE]

    def __init__(self, bot):
        super().__init__(bot)
        self.tags = {}

        Tag.inject_bot(self.bot)

        super(AinitMixin).__init__()

    async def _ainit(self):
        await self.bot.wait_until_ready()

        async with self.bot.Session() as session:
            _tags = await db.get_tags(session)

            for tag in _tags:
                if tag.guild:  # ignore guilds that the bot is not in
                    self._get_tags(tag.guild).append(tag)

        logger.info(
            f"# Initial tags from db: {sum([len(guild_tags) for guild_tags in self.tags.values()])}"
        )

    async def _get_tags_by_trigger(self, trigger, guild, fuzzy=75):
        if not fuzzy:
            tags = [
                tag
                for tag in self._get_tags(guild)
                if tag.trigger.lower() == trigger.lower()
            ]
        else:
            tags = [
                tag
                for tag in self._get_tags(guild)
                if ratio(tag.trigger.lower(), trigger.lower()) > fuzzy
            ]
        return tags

    async def _get_duplicates(self, trigger, reaction, guild):
        return [
            tag
            for tag in self._get_tags(guild)
            if (
                tag.trigger == trigger
                and tag.reaction == reaction
                and tag.guild == guild
            )
        ]

    def _get_tags(self, guild: discord.Guild):
        return self.tags.setdefault(guild.id, [])

    async def _invoke_tag(self, channel, tag, info=False):
        if info:
            await channel.send(
                f"**{tag.trigger}** (`{tag.tag_id}`) by {tag.creator}\n{tag.reaction}"
            )
        else:
            await channel.send(tag.reaction)

        async with self.bot.Session() as session:
            await tag.increment_use_count(session)
            await session.commit()

    @auto_help
    @commands.group(
        name="tags",
        aliases=["tag"],
        invoke_without_command=True,
        brief="Manage custom reactions",
    )
    async def tag(self, ctx, *, args=None):
        await ctx.invoke(self.list, dm=args)

    @tag.command(aliases=["new", "create"], brief="Adds a new tag")
    async def add(
        self,
        ctx,
        in_msg: typing.Optional[bool] = False,
        trigger: commands.clean_content = "",
        reaction_attachment: typing.Optional[discord.Attachment] = None,
        *,
        reaction_text: typing.Optional[commands.clean_content] = "",
    ):
        """
        Adds a new tag.

        Example usage:
        `{prefix}tag add wave https://gfycat.com/BenvolentCurteousGermanpinsher`

        Attach picture to the message and type:
        `{prefix}tag add "doggo pic"`

        To scan the entire message for the trigger **haha**:
        `{prefix}tag add true haha stop laughing`
        """
        reaction = reaction_attachment.url if reaction_attachment else reaction_text

        if len(trigger) == 0 or len(reaction) == 0:
            raise commands.BadArgument(
                "A tag needs both a trigger phrase and a reaction (as an attachment or text)."
            )

        matches = await self._get_duplicates(trigger, reaction, ctx.guild)

        if len(matches) > 0:
            raise commands.BadArgument(
                f"This tag already exists (`{matches[0].tag_id}`)."
            )
        else:
            async with self.bot.Session(expire_on_commit=False) as session:
                tag = Tag(
                    trigger=trigger,
                    reaction=reaction.url
                    if type(reaction) is discord.Attachment
                    else reaction,
                    in_msg=in_msg,
                    _creator=ctx.author.id,
                    _guild=ctx.guild.id,
                )
                session.add(tag)
                await session.commit()

                self._get_tags(ctx.guild).append(tag)
                await ctx.send(f"Tag `{tag.tag_id}` has been created.")

    @tag.command(aliases=["remove"], brief="Deletes given tag")
    async def delete(self, ctx, tag: TagConverter):
        """
        Deletes the given tag.

        Example usage:
        Deletion by ID:
        `{prefix}tag delete 45`

        Deletion by trigger:
        `{prefix}tag delete haha`
        """
        # only allow tag owner and admins to delete tags
        if tag.creator != ctx.author and not ctx.author.guild_permissions.administrator:
            raise commands.BadArgument("You're not this tag's owner.")
        else:
            confirm = await Confirm(
                f"Are you sure you want to delete the tag with ID {tag.tag_id}, "
                f"trigger `{tag.trigger}` and reaction {tag.reaction}?"
            ).prompt(ctx)

            if confirm:
                async with self.bot.Session() as session:
                    await tag.delete(session)
                    self._get_tags(ctx.guild).remove(tag)
                    await session.commit()

                await ctx.send(f"Tag `{tag.tag_id}` was deleted.")

    @tag.command(aliases=["change"], brief="Edits given tag")
    async def edit(self, ctx, tag: TagConverter, key, *, value: commands.clean_content):
        """
        Edits the given tag.

        Example usage:
        Make the tag `haha` trigger on parts of the message:
        `{prefix}tag edit haha in_msg true`

        Make the tag `haha` trigger on `hehe` instead:
        `{prefix}tag edit haha trigger hehe`

        Change `haha`'s reaction to `stop laughing`:
        `{prefix}tag edit haha reaction stop laughing`
        """
        # only allow tag owner and admins to edit tags
        if tag.creator != ctx.author and not ctx.author.guild_permissions.administrator:
            raise commands.BadArgument("You're not this tag's owner.")

        elif key not in Tag.EDITABLE:
            raise commands.BadArgument(
                f'Cannot edit `{key}`. Valid choices: {", ".join(self.FORMATTED_KEYS)}.'
            )
        else:
            if key == "in_msg":
                value = await BoolConverter().convert(ctx, value)
            elif key in ["trigger", "reaction"]:
                # check whether we are creating a duplicate
                matches = await self._get_duplicates(
                    value if key == "trigger" else tag.trigger,
                    value if key == "reaction" else tag.reaction,
                    ctx.guild,
                )
                if len(matches) > 0:
                    raise commands.BadArgument(
                        f"This edit would create a duplicate of tag `{matches[0].tag_id}`."
                    )

            old_value = getattr(tag, key)

            async with self.bot.Session() as session:
                await tag.update(session, key, value)
                await session.commit()

            await ctx.send(f"Tag `{tag.tag_id}` was edited. Old {key}:\n{old_value}")

    @guild_has_tags()
    @auto_help
    @tag.group(
        brief="Sends a list of all tags in the server", invoke_without_command=True
    )
    async def list(self, ctx):
        """
        Sends a list of all tags in the server.
        """
        pages = MenuPages(
            source=TagListSource(self._get_tags(ctx.guild)), clear_reactions_after=True
        )
        await pages.start(ctx)

    @list.command(name="detail", brief="Sends a detailed list")
    async def list_detail(self, ctx):
        """
        Sends a detailed list of all tags in the server.
        """
        pages = MenuPages(
            source=DetailTagListSource(self._get_tags(ctx.guild)),
            clear_reactions_after=True,
        )
        await pages.start(ctx)

    @tag.group(
        aliases=["search"],
        brief="Displays some info about a tag",
        invoke_without_command=True,
    )
    async def info(self, ctx, *, tag: TagConverter(prompt_selection=False)):
        """
        Displays some info about a tag.

        Example usage:
        Query by ID:
        `{prefix}tag info 45`

        Query by trigger:
        `{prefix}tag info haha`
        """
        if type(tag) is list:
            await ctx.send(
                "Choose a tag by reacting with the corresponding number.",
                delete_after=10,
            )
            pages = SelectionMenu(source=TagListSource(tag))
            selection = await pages.prompt(ctx)
        else:
            selection = tag

        await ctx.send(embed=selection.info_embed())

    @info.command(name="detail")
    async def info_detail(self, ctx, *, tag: TagConverter(prompt_selection=False)):
        if type(tag) is list:
            pages = SelectionMenu(source=DetailTagListSource(tag))
            await pages.prompt(ctx)
        else:
            await ctx.send(embed=tag.info_embed())

    @guild_has_tags()
    @tag.command(brief="Sends a random tag")
    async def random(self, ctx):
        await self._invoke_tag(ctx, random.choice(self._get_tags(ctx.guild)), info=True)

    @list.error
    @random.error
    async def guild_has_no_tags_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("Try to add a few tags first.")

    @commands.Cog.listener("on_message")
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
