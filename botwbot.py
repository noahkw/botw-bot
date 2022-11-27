import logging
import typing
from collections import Counter

import discord
from discord.ext import commands
from discord.ext.commands import Cog

import const
import db
from const import CUSTOM_EMOJI
from help_command import EmbedHelpCommand
from log import MessageableHandler
from models import GuildCog
from util import safe_send, ChannelLocker

logger = logging.getLogger(__name__)


class BotwBot(commands.Bot):
    CREATOR_ID = 207955387909931009
    PRIVILEGED_COGS = {"Instagram"}

    def __init__(self, config, **kwargs):
        # the Session is attached by the launcher script
        self.Session = None
        self.config = config

        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            **kwargs,
            command_prefix=self.config["discord"]["command_prefix"],
            help_command=EmbedHelpCommand(),
            intents=intents,
            allowed_mentions=discord.AllowedMentions(
                everyone=False, users=True, roles=False
            ),
        )
        self.add_checks()

        # ban after more than 5 commands in 10 seconds
        self.spam_cd = commands.CooldownMapping.from_cooldown(
            5, 10, commands.BucketType.user
        )
        self._spam_count = Counter()
        self.blacklist = set()

        self.prefixes = {}  # guild.id -> prefix
        self.whitelist = set()  # guild.id
        self.custom_emoji = {}  # name -> Emoji instance

        self.channel_locker = ChannelLocker()

        GuildCog.inject_bot(self)

        self.privileged_cogs_cache: dict[str, set[int]] = {}

    async def on_ready(self):
        await self.change_presence(activity=discord.Game("with Bini"))

        if self.Session:
            async with self.Session() as session:
                # cache guild prefixes and whitelist
                settings = await db.get_guild_settings(session)
                for guild_settings in settings:
                    if prefix := guild_settings.prefix:
                        self.prefixes[guild_settings._guild] = prefix

                    if guild_settings.whitelisted:
                        self.whitelist.add(guild_settings._guild)

        for name, emoji_name in CUSTOM_EMOJI.items():
            emoji = discord.utils.find(lambda e: e.name == emoji_name, self.emojis)
            if emoji is None:
                raise ValueError(
                    f"Could not find emoji '{emoji_name}'. Maybe the bot cannot see it?"
                )

            self.custom_emoji[name] = emoji

        for ext in self.config["enabled_cogs"]:
            await self.load_extension(ext)

        logging_channel = self.get_channel(self.config["logging"]["channel_id"])
        if logging_channel:
            handler = MessageableHandler(logging_channel)
            handler.setFormatter(
                logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
            )
            logging.getLogger().addHandler(handler)
        else:
            logger.info(
                "Logging to discord channel disabled because messageable ID (%s) invalid",
                self.config["logging"]["channel_id"],
            )

        logger.info(
            "Logged in as %s. Whitelisted servers: %s", self.user, self.whitelist
        )

    async def on_disconnect(self):
        logger.debug("disconnected")

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(
            error, (commands.CommandNotFound, discord.ext.menus.MenuError)
        ) or hasattr(ctx.command, "on_error"):
            return

        error = getattr(error, "original", error)

        if isinstance(error, discord.Forbidden):
            try:
                await ctx.message.add_reaction(const.UNICODE_EMOJI["CROSS"])
                return
            except discord.Forbidden:
                # We tried...
                return

        if isinstance(
            error,
            (
                commands.BadArgument,
                commands.MissingRequiredArgument,
                commands.MissingPermissions,
                commands.DisabledCommand,
                commands.CommandOnCooldown,
                commands.NotOwner,
                commands.BotMissingPermissions,
                commands.CheckFailure,
            ),
        ):
            message = await safe_send(ctx, str(error))

            if message:
                return

        logger.exception(error)

    async def whitelisted_or_leave(self, guild: typing.Optional[discord.Guild]):
        """
        Returns False and logs a message if the passed guild is not whitelisted.
        """
        whitelisted = (
            guild is None
            or self.Session is None
            or guild.owner == self.user
            or guild.id in self.whitelist
        )

        if not whitelisted:
            owner = guild.owner
            logger.info(
                f"Consider leaving non-whitelisted guild {guild.name} ({guild.id})"
                + (
                    f" Owner: {guild.owner.name} ({guild.owner.id})"
                    if owner
                    else "(owner not in cache)"
                )
            )

        return whitelisted

    def add_checks(self):
        async def globally_block_dms(ctx):
            return ctx.guild is not None or await self.is_owner(ctx.author)

        self.add_check(globally_block_dms)

    async def get_prefix(self, message):
        if not message.guild:
            return self.command_prefix

        prefix = self.prefixes.setdefault(message.guild.id, self.command_prefix)

        return commands.when_mentioned_or(prefix)(self, message)

    async def on_message(self, message: discord.Message):
        if not self.is_ready() or not (await self.whitelisted_or_leave(message.guild)):
            # Ignore commands in non-whitelisted guilds
            return

        await self.process_commands(message)

    def invalidate_privileged_cog_cache(self, cog_name: str):
        self.privileged_cogs_cache.pop(cog_name)

    async def get_guilds_for_cog(self, cog: Cog) -> typing.Optional[set[discord.Guild]]:
        cog_name = cog.__cog_name__

        if cog_name not in self.PRIVILEGED_COGS:
            return None

        guilds = self.privileged_cogs_cache.get(cog_name)
        if guilds is not None:
            return {self.get_guild(guild) for guild in guilds}

        async with self.Session() as session:
            guilds = await db.get_cog_guilds(session, cog_name)
            self.privileged_cogs_cache[cog_name] = {guild._guild for guild in guilds}

            guild_objs = {guild.guild for guild in guilds}
            logger.info(
                "Added guilds for privileged cog %s: %s",
                cog_name,
                ", ".join([str(guild_obj) for guild_obj in guild_objs]),
            )

            return guild_objs

    async def process_commands(self, message):
        ctx = await self.get_context(message)

        if ctx.command is None or message.author.id in self.blacklist:
            return

        # spam control
        bucket = self.spam_cd.get_bucket(message)
        retry_after = bucket.update_rate_limit()

        if retry_after and message.author.id != self.owner_id:
            await message.channel.send(
                f"{message.author.mention}, stop spamming and retry when this message is deleted!",
                delete_after=retry_after + 5,
            )

            self._spam_count[message.author.id] += 1

            if self._spam_count[message.author.id] >= 5:
                self.blacklist.add(message.author.id)
                await message.channel.send(
                    f"{message.author.mention}, you have been blacklisted from using commands!"
                )

            return
        else:
            self._spam_count.pop(message.author.id, None)

        await super().process_commands(message)
