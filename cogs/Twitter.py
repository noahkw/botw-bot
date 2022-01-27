import asyncio
import copy
import logging
import re
import time
import typing
from datetime import datetime, timedelta
from io import BytesIO

import aiohttp
import discord
import peony
from discord import File
from discord.ext import commands
from discord.ext.menus import MenuPages
from peony import PeonyClient, events

import db
from cogs import CustomCog, AinitMixin
from const import UNICODE_EMOJI
from menu import SimpleConfirm
from menu import TwitterListSource
from models import TwtSetting, TwtAccount, TwtSorting, TwtFilter
from util import auto_help, ack, ReactingRetryingSession, ExceededMaximumRetries

logger = logging.getLogger(__name__)


@events.priority(-15)
def on_tweet_with_media(data):
    """Event triggered when the data corresponds to a tweet with a media"""
    return "media" in data.get("entities", {})


def setup(bot):
    bot.add_cog(Twitter(bot))


class TwitterNotEnabled(commands.CheckFailure):
    def __init__(self):
        super().__init__("Twitter has not been enabled in this server.")


def twitter_enabled():
    async def predicate(ctx):
        async with ctx.bot.Session() as session:
            twitter_settings = await db.get_twitter_settings(
                session, guild_id=ctx.guild.id
            )

            if not (twitter_settings and twitter_settings.enabled):
                raise TwitterNotEnabled
            else:
                return True

    return commands.check(predicate)


class Twitter(CustomCog, AinitMixin):
    FILESIZE_MAX = 8 * 10 ** 6  # 8 MB
    URL_REGEX = r"(https?://)?(www.)?twitter.com/(\S+)/status/(\d+)(\?s=\d+)?"
    EVENT_DATE_REGEX = r"(\s+|^)(\d{6}|\d{8})\s*"
    TEST_TWEET_ID = 1230927030163628032
    KR_UTC_OFFSET = timedelta(hours=9)
    RESTART_STREAM_COOLDOWN = 2 * 60  # 2 minutes
    MAX_RETRIES = 3
    TWITTER_REQ_SIZE = 100

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.feed = None
        self.stream_thing = None
        self.client = None
        self.stream_task = None
        self.restart_stream_task = None
        self.session = aiohttp.ClientSession()
        self.keys = self.bot.config["cogs"]["twitter"]
        TwtSorting.inject_bot(self.bot)
        TwtSetting.inject_bot(self.bot)
        super(AinitMixin).__init__()

    async def _ainit(self):
        self.client = PeonyClient(**self.keys, loop=self.bot.loop)
        self.restart_stream_task = asyncio.create_task(self.restart_stream_sub())

    def cog_unload(self):
        if self.stream_task:
            self.stream_task.cancel()

        if self.restart_stream_task:
            self.restart_stream_task.cancel()

        asyncio.create_task(self.session.close())

    async def generate_accounts(self, session):
        accounts_list = set(await db.get_twitter_accounts_distinct(session))
        logger.debug("Generated new accounts list with %d accounts", len(accounts_list))
        return accounts_list

    async def streaming(self):
        self.feed = self.client.stream.statuses.filter.post(follow=self.gen_accounts)

        async with self.feed as stream:
            self.stream_thing = stream
            async for tweet in self.stream_thing:
                if (
                    on_tweet_with_media(tweet)
                    and tweet.user.id_str in self.gen_accounts
                    and "quoted_status" not in tweet
                    and "retweeted_status" not in tweet
                ):
                    logger.debug(
                        "Processing @%s - %s", tweet.user.screen_name, tweet.id_str
                    )
                    async with self.bot.Session() as session:
                        try:
                            await self.manage_twt(tweet, session)
                        except Exception:
                            logger.exception("Error processing tweet")

    async def restart_stream(self):
        if self.restart_stream_task.done():
            self.restart_stream_task = asyncio.create_task(
                self.restart_stream_sub(wait_time=self.RESTART_STREAM_COOLDOWN)
            )

    async def restart_stream_sub(self, wait_time=0):
        await asyncio.sleep(wait_time)
        async with self.bot.Session() as session:
            self.gen_accounts = await self.generate_accounts(session)
            if self.stream_task:
                self.stream_task.cancel()
            if self.gen_accounts:
                logger.info("Started stream with %d accounts", len(self.gen_accounts))
                self.stream_task = asyncio.create_task(self.streaming())

    async def manage_twt(self, tweet, session):
        tags_list = [tag.text for tag in tweet.entities.hashtags]
        if tags_list:
            server_list_accs = await db.get_twitter_accounts(
                session, account_id=tweet.user.id_str
            )
            server_list_accs = [server._guild for server in server_list_accs]
            tweet_text = tweet.full_text if "full_text" in tweet else tweet.text
            server_list = await self.get_servers(session, server_list_accs, tweet_text)
            if server_list:
                channels_list = await self.get_channels(
                    servers=server_list, tags=tags_list, session=session
                )
                tweet_txt, file_list = await self.create_post(tweet)
                await self.manage_post_tweet(tweet_txt, file_list, channels_list)

    async def get_account(self, ctx, account):
        try:
            account_id = await self.client.api.users.show.get(screen_name=account)
        except peony.exceptions.UserNotFound:
            raise commands.BadArgument(f"User `{account}` not found.")
        except (peony.exceptions.UserSuspended, peony.exceptions.AccountSuspended):
            raise commands.BadArgument(f"User `{account}` is suspended.")
        except peony.exceptions.AccountLocked:
            raise commands.BadArgument(f"User `{account}` is locked.")
        except peony.exceptions.PeonyException:
            logger.exception("Error finding account %s", account)
            raise commands.BadArgument(f"Error finding account `{account}`.")

        return account_id

    async def get_tweet(self, ctx, tweet_id):
        try:
            tweet = await self.client.api.statuses.show.get(
                id=tweet_id,
                include_entities=True,
                tweet_mode="extended",
            )
        except (peony.exceptions.StatusNotFound, peony.exceptions.HTTPNotFound):
            await ctx.send("Tweet not found")
            return None

        return tweet

    async def get_servers(self, session, server_list, tweet_txt):
        server_set = set(server_list)
        tweet_words = tweet_txt.split()
        filtered_servers = await db.get_twitter_filters(
            session, guild_list=server_list, word_list=tweet_words
        )
        disabled_servers = await db.get_twitter_settings(
            session, guild_list=server_list, disabled_servers=True
        )
        filtered_servers = set([srv._guild for srv in filtered_servers])
        disabled_servers = set([srv._guild for srv in disabled_servers])
        filtered_servers = filtered_servers | disabled_servers

        return list(server_set - filtered_servers)

    async def get_channels(self, servers, tags, session):
        servers_channels_raw = await db.get_twitter_sorting(
            session, tag_list=tags, guild_list=servers
        )
        servers_dict = {server._guild: set() for server in servers_channels_raw}

        # get channels into dict per server
        for server in servers_channels_raw:
            # just one of each, so we use a set since
            # multiple hashtags can map to the same channel
            servers_dict[server._guild].add(server.channel)

        channel_list = []
        for server_id in servers_dict:
            if len(servers_dict[server_id]) > 1:
                server_settings = await db.get_twitter_settings(
                    session, guild_id=server_id
                )
                if server_settings.default_channel:
                    channel_list.append(server_settings.default_channel)
                else:
                    channel_list.extend(servers_dict[server_id])
            else:
                channel_list.extend(servers_dict[server_id])

        return channel_list

    async def create_post(self, tweet, is_stream=True, message=None):
        tweet_date = datetime.strptime(tweet.created_at, "%a %b %d %H:%M:%S %z %Y")
        tweet_date = (tweet_date + self.KR_UTC_OFFSET).strftime("%y%m%d")

        event_date = re.search(self.EVENT_DATE_REGEX, tweet.text)
        date = event_date.group(2)[-6:] if event_date else tweet_date

        username = tweet.user.screen_name
        files = []

        post_format = "`{0} - cr: @{1}`\n<https://twitter.com/{1}/status/{2}>\n"
        if is_stream:
            post = post_format.format(date, username, tweet.id)
        else:
            post = ""

        if "video_info" in tweet.extended_entities.media[0]:
            variants = tweet.extended_entities.media[0]["video_info"]["variants"]
            bitrate_and_urls = [
                (variant["bitrate"], variant["url"])
                for variant in variants
                if "bitrate" in variant
            ]
            video_url = max(bitrate_and_urls, key=lambda x: x[0])[1]
            video_filename = video_url.split("/")[-1].split("?")[0]

            try:
                async with ReactingRetryingSession(
                    self.MAX_RETRIES,
                    self.session.get,
                    video_url,
                    message=message,
                    emoji=self.bot.custom_emoji["RETRY"],
                ) as response:
                    video_bytes = BytesIO(await response.read())

                    if video_bytes.getbuffer().nbytes < self.FILESIZE_MAX:
                        files.append(File(video_bytes, filename=video_filename))
                        post += f"\n<{video_url}>"
                    else:
                        post += f"\n{video_url}"
            except ExceededMaximumRetries as e:
                logger.info(
                    "Unable to download video '%s' after %d retries", e.url, e.tries
                )
                post += f"\n{video_url}"

        else:
            download_results = await asyncio.gather(
                *[
                    self.download_pic(
                        image.media_url.split("/")[-1],
                        image.media_url + "?name=orig",
                        message,
                    )
                    for image in tweet.extended_entities.media
                ]
            )

            pic_files, pic_urls = zip(*download_results)

            post += "\n".join(pic_urls)
            files.extend(file for file in pic_files if file is not None)

        return post, files

    async def download_pic(
        self, filename: str, url: str, message=None
    ) -> tuple[typing.Optional[discord.File], str]:
        try:
            async with ReactingRetryingSession(
                self.MAX_RETRIES,
                self.session.get,
                url,
                message=message,
                emoji=self.bot.custom_emoji["RETRY"],
            ) as response:
                return File(BytesIO(await response.read()), filename), f"<{url}>"
        except ExceededMaximumRetries as e:
            logger.info(
                "Unable to download picture '%s' after %d retries", e.url, e.tries
            )
            return None, url

    async def manage_post_tweet(self, post, files, channels):
        post_list = []
        for channel in channels:
            post_list.append(self.post_tweet(post, copy.deepcopy(files), channel))
        await asyncio.gather(*post_list)

    async def post_tweet(self, post, files, channel):
        await channel.send(post)
        for file in files:
            await channel.send(file=file)

    @auto_help
    @commands.group(
        name="twitter",
        aliases=["twt"],
        brief="Automatically post twitter pics to specific channels based on tags and accounts",
    )
    async def twitter(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.twitter)

    @twitter.command(brief="Prints Twitter Stats")
    @commands.is_owner()
    async def stats(self, ctx):
        accts_followed = len(self.gen_accounts)
        time_start = time.time()
        await self.client.api.statuses.show.get(id=self.TEST_TWEET_ID)
        time_end = time.time()
        stats_embed = discord.Embed()
        stats_embed.set_author(name="Twitter Cog Global Stats")
        stats_embed.add_field(
            name="Number Accounts Followed", value=f"{accts_followed}", inline=False
        )
        stats_embed.add_field(
            name="Twitter API Latency",
            value=f"{(time_end - time_start) * 1000:.2f} ms",
            inline=False,
        )
        await ctx.send(embed=stats_embed)

    @twitter.command(brief="Enable Twitter pic posting on server")
    @commands.has_permissions(administrator=True)
    @ack
    async def enable(self, ctx):
        """
        Enables Twitter pic posting on the server, can specify the default channel

        Example usage:
        `{prefix}twitter enable`
        """
        async with self.bot.Session() as session:
            server_settings = await db.get_twitter_settings(
                session, guild_id=ctx.guild.id
            )
            if server_settings:
                if server_settings.enabled:
                    await ctx.send(f"Twitter already enabled for {ctx.guild.name}")
                else:
                    logger.info(
                        "%s (%d) re-enabled twitter", ctx.guild.name, ctx.guild.id
                    )
                    server_settings.enabled = True
            else:
                server_settings = TwtSetting(
                    _guild=ctx.guild.id,
                    _default_channel=0,
                    enabled=True,
                )
                session.add(server_settings)
                logger.info("%s (%d) enabled twitter", ctx.guild.name, ctx.guild.id)
            await session.commit()

    @twitter.command(brief="Disable Twitter pic posting on server")
    @commands.has_permissions(administrator=True)
    @twitter_enabled()
    @ack
    async def disable(self, ctx):
        """
        Enables Twitter pic posting on the server, can specify the default channel

        Example usage:
        `{prefix}twitter enable`
        """
        async with self.bot.Session() as session:
            server_settings = await db.get_twitter_settings(
                session, guild_id=ctx.guild.id
            )
            server_settings.enabled = False
            logger.info("%s (%d) disabled twitter", ctx.guild.name, ctx.guild.id)
            await session.commit()

    @twitter.command(brief="Post tweet as if caught from stream")
    @commands.has_permissions(manage_messages=True)
    @twitter_enabled()
    @ack
    async def post(
        self,
        ctx,
        tweet_url: commands.clean_content,
        channel: discord.TextChannel = None,
    ):
        """
        Will post individual tweet using sorting methods as implemented with hashtags by server,
        or to a specific channel

        Example usage:
        {prefix}twitter post https://twitter.com/Mias_Other_Half/status/1379979650605137928
        or
        {prefix}twitter post https://twitter.com/Mias_Other_Half/status/1379979650605137928 #pics
        """
        tweet_urls = re.finditer(self.URL_REGEX, tweet_url)
        tweet_ids = [tweet_url_.group(4) for tweet_url_ in tweet_urls]

        if tweet_ids:
            for tweet_id in tweet_ids:
                tweet = await self.get_tweet(ctx, tweet_id)
                if tweet:
                    logger.debug(
                        "Processing: @%s - %s in %s (%d)",
                        tweet.user.screen_name,
                        tweet.id_str,
                        ctx.guild.name,
                        ctx.guild.id,
                    )
                    tags_list = [tag.text for tag in tweet.entities.hashtags]
                    if channel:
                        channels_list = [channel]
                    else:
                        async with self.bot.Session() as session:
                            channels_list = await self.get_channels(
                                servers=[ctx.guild.id], tags=tags_list, session=session
                            )
                    tweet_txt, file_list = await self.create_post(tweet)
                    await self.manage_post_tweet(tweet_txt, file_list, channels_list)

    @twitter.group(
        name="configure",
        aliases=["config"],
        brief="Set server specific details, default_channel",
    )
    @twitter_enabled()
    async def configure(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.configure)

    @configure.command(
        name="default_channel",
        brief="Add a channel for tweets that match multiple channels to be placed into",
    )
    @twitter_enabled()
    @commands.has_permissions(manage_messages=True)
    @ack
    async def default_channel(self, ctx, channel: discord.TextChannel = None):
        """
        Set a default channel for when multiple channels match a tweet.
        Such as #group or #OT5 or #<Group_Name>
        Leave unset to have tweet posted in all matching channels
        Leave blank to clear default channel
        """
        async with self.bot.Session() as session:
            server_settings = await db.get_twitter_settings(
                session, guild_id=ctx.guild.id
            )
            server_settings._default_channel = channel.id if channel else 0

            await session.commit()

    @twitter.group(
        name="add",
        brief="Add sorting strategies based on channels, tags, and accounts",
    )
    @twitter_enabled()
    @commands.has_permissions(manage_messages=True)
    async def add(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.add)

    @add.command(
        name="hashtag",
        brief="Add a channel for a member's pictures or videos to be posted in",
    )
    @ack
    async def add_hashtag(
        self, ctx, hashtag: commands.clean_content, channel: discord.TextChannel
    ):
        """
        Associates a hashtag with a specific channel, more than one hashtag can be associated with any channel

        Example usage:
        `{prefix}twitter add hashtag <hashtag> <channel> `
        `{prefix}twitter add hashtag 아이린 #Irene`
        """
        # in case they enter it with the hashtag character
        tag_conditioned = hashtag.split("#")[-1]
        # check if hashtag already exists
        async with self.bot.Session() as session:
            twitter_sorting = await db.get_twitter_sorting(
                session, hashtag=tag_conditioned, guild_id=ctx.guild.id
            )
            if twitter_sorting:
                await db.delete_twitter_sorting(session, tag_conditioned, ctx.guild.id)
                logger.debug(
                    "%s (%d) updated %s to %s",
                    ctx.guild.name,
                    ctx.guild.id,
                    tag_conditioned,
                    channel,
                )
                await ctx.send(f"#{tag_conditioned} channel updated to {channel}")
            else:
                logger.info(f"{ctx.guild.name} added {tag_conditioned} to #{channel}")

            twitter_sorting = TwtSorting(
                _guild=ctx.guild.id, hashtag=tag_conditioned, _channel=channel.id
            )
            session.add(twitter_sorting)

            await session.commit()

    @add.command(
        name="filter",
        brief="Add a word filter to skip posting tweets",
    )
    @ack
    async def add_filter(self, ctx, filter_: commands.clean_content):
        """
        Add a filter to your tweet stream, any tweets containing these filters will not be posted.

        Example usage:
        `{prefix}twitter add filter 프리뷰`
        """
        async with self.bot.Session() as session:
            # check if filter already exists
            twitter_filter = await db.get_twitter_filters(
                session, filter_=filter_, guild_id=ctx.guild.id
            )
            if twitter_filter:
                await ctx.send(f'Filter "{filter_}" already exists')
            else:
                twitter_filter = TwtFilter(_guild=ctx.guild.id, _filter=filter_)
                logger.debug(
                    "%s (%d) added filter - %s", ctx.guild.name, ctx.guild.id, filter_
                )
                session.add(twitter_filter)
                await session.commit()

    @add.command(name="account", brief="Add a twitter account for the server to follow")
    async def add_account(self, ctx, *accounts: commands.clean_content):
        """
        Adds one or multiple twitter accounts for a server to follow, to be sorted by associated tags into channels.

        Example usage:
        `{prefix}twitter add account thinkB329`
        `{prefix}twitter add account less_than_333 justcuz810`
        """
        # in case they enter it with the @ character
        accounts_conditioned = [account.split("@")[-1].lower() for account in accounts]
        try:
            accounts = await self.client.api.users.lookup.get(
                screen_name=accounts_conditioned
            )
        except peony.exceptions.NoUserMatchesQuery:
            raise commands.BadArgument(
                "Could find no matches for the specified accounts."
            )

        accounts_found = [account.screen_name.lower() for account in accounts]
        accounts_not_found = list(set(accounts_conditioned) - set(accounts_found))

        async with self.bot.Session() as session:
            followed_account_ids = set(
                account.account_id
                for account in await db.get_twitter_accounts(
                    session, guild_id=ctx.guild.id
                )
            )
            session.add_all(
                [
                    TwtAccount(_guild=ctx.guild.id, account_id=account.id_str)
                    for account in accounts
                    if account.id_str not in followed_account_ids
                ]
            )

            await session.commit()

        logger.info(
            "%s (%d) added account(s) %s", ctx.guild.name, ctx.guild.id, accounts_found
        )

        embed = discord.Embed(title="Followed Accounts")
        if len(accounts_found) > 0:
            embed.add_field(
                name=f"Successfully followed {UNICODE_EMOJI['CHECK']}",
                value="\n".join(accounts_found),
            )
        if len(accounts_not_found) > 0:
            embed.add_field(
                name=f"Not found {UNICODE_EMOJI['CROSS']}",
                value="\n".join(accounts_not_found),
            )

        await ctx.send(embed=embed)

        await self.restart_stream()

    @twitter.group(
        name="remove",
        brief="Remove sorting strategies based on channels, tags, and accounts",
    )
    @twitter_enabled()
    @commands.has_permissions(manage_messages=True)
    async def remove(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.remove)

    @remove.command(
        name="hashtag",
        brief="Remove a channel for a member's pictures or videos to be posted in",
    )
    @ack
    async def remove_hashtag(self, ctx, hashtag: commands.clean_content):
        """
        Removes a hashtag

        Example usage:
        `{prefix}twitter remove 아이린`
        """
        # in case they enter it with the hashtag character
        tag_conditioned = hashtag.split("#")[-1]
        async with self.bot.Session() as session:
            logger.info(
                "%s (%d) deleted hashtag %s",
                ctx.guild.name,
                ctx.guild.id,
                tag_conditioned,
            )
            await db.delete_twitter_sorting(session, tag_conditioned, ctx.guild.id)
            await session.commit()

    @remove.command(
        name="account", brief="Add a twitter account for the server to follow"
    )
    @ack
    async def remove_account(self, ctx, account: commands.clean_content):
        """
        Unfollows a twitter account for the server

        Example usage:
        `{prefix}twitter remove account thinkB329`
        """
        # in case they enter it with the @ character
        account_conditioned = account.split("@")[-1]
        account = await self.get_account(ctx, account=account_conditioned)

        async with self.bot.Session() as session:
            logger.info(
                "%s (%d) removed account %s",
                ctx.guild.name,
                ctx.guild.id,
                account.id_str,
            )
            await db.delete_accounts(session, account.id_str, ctx.guild.id)
            await session.commit()
            await self.restart_stream()

    @remove.command(
        name="filter",
        brief="Remove a word filter to skip posting tweets",
    )
    @ack
    async def remove_filter(self, ctx, filter_: commands.clean_content):
        """
        Remove a filter to your tweet stream, any tweets containing these filters will not be posted.

        Example usage:
        `{prefix}twitter remove filter 프리뷰`
        """
        async with self.bot.Session() as session:
            await db.delete_twitter_filters(
                session, _filter=filter_, guild_id=ctx.guild.id
            )
            logger.info(
                "%s (%d) removed filter - %s", ctx.guild.name, ctx.guild.id, filter_
            )
            await session.commit()

    @twitter.group(
        name="show",
        brief="Show what accounts or sorting strategies currently enabled",
    )
    @twitter_enabled()
    @commands.has_permissions(manage_messages=True)
    async def show(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.show)

    @show.command(name="accounts", brief="List all accounts followed by this server")
    async def show_accounts(self, ctx):
        async with self.bot.Session() as session:
            accounts_followed = await db.get_twitter_accounts(
                session, guild_id=ctx.guild.id
            )

        if len(accounts_followed) == 0:
            raise commands.BadArgument(
                f"Follow some accounts first: `{ctx.prefix}help twt add account`"
            )

        accounts_followed = [guild.account_id for guild in accounts_followed]
        split_accounts_followed = [
            accounts_followed[i : i + self.TWITTER_REQ_SIZE]
            for i in range(0, len(accounts_followed), self.TWITTER_REQ_SIZE)
        ]

        twitter_tasks = []
        for split in split_accounts_followed:
            twitter_tasks.append(self.client.api.users.lookup.get(user_id=split))
        split_user_list = await asyncio.gather(*twitter_tasks)
        user_name_list = [account for split in split_user_list for account in split]

        value_strings = [
            f"@{account.screen_name} - {account.name}" for account in user_name_list
        ]
        accounts_pages = MenuPages(
            source=TwitterListSource(value_strings, "Accounts Followed"),
            clear_reactions_after=True,
        )

        await accounts_pages.start(ctx)

    @show.command(
        name="hashtags", brief="List all hashtags and channels for this server"
    )
    async def show_hashtags(self, ctx):
        async with self.bot.Session() as session:
            channels_list = await db.get_twitter_sorting(session, guild_id=ctx.guild.id)

        if len(channels_list) == 0:
            raise commands.BadArgument(
                f"Add some hashtags first: `{ctx.prefix}help twt add hashtag`"
            )

        value_strings = [
            f"#{server.hashtag} - {server.channel.mention}" for server in channels_list
        ]
        hash_pages = MenuPages(
            source=TwitterListSource(value_strings, "Hashtag to Channel Map"),
            clear_reactions_after=True,
        )

        await hash_pages.start(ctx)

    @show.command(name="filters", brief="List all tweet filters for this server")
    async def show_filters(self, ctx):
        async with self.bot.Session() as session:
            filters_list = await db.get_twitter_filters(session, guild_id=ctx.guild.id)

        if len(filters_list) == 0:
            raise commands.BadArgument(
                f"Add some filters first: `{ctx.prefix}help twt add filter`"
            )

        value_strings = [filter_._filter for filter_ in filters_list]
        accounts_pages = MenuPages(
            source=TwitterListSource(value_strings, "Server Tweet Filters"),
            clear_reactions_after=True,
        )

        await accounts_pages.start(ctx)

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)
        if ctx.valid or not ctx.guild or message.webhook_id or message.author.bot:
            return

        results = re.finditer(self.URL_REGEX, message.content)
        tweet_ids = [result.group(4) for result in results]

        if tweet_ids:
            confirm = await SimpleConfirm(
                message, emoji=UNICODE_EMOJI["INSPECT"]
            ).prompt(ctx)
            if confirm:
                async with ctx.typing():
                    for tweet_id in tweet_ids:
                        tweet = await self.get_tweet(ctx, tweet_id)
                        if tweet and "extended_entities" in tweet:
                            try:
                                await ctx.message.edit(suppress=True)
                            except discord.Forbidden:
                                pass
                            tweet_txt, file_list = await self.create_post(
                                tweet, is_stream=False, message=message
                            )
                            await self.post_tweet(tweet_txt, file_list, ctx.channel)
