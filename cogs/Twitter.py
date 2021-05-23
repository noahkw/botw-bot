import asyncio
import logging
import aiohttp
import datetime
import peony
from peony import PeonyClient, events
import re
import discord
import db
import time
import copy
from const import INSPECT_EMOJI
from menu import SimpleConfirm
from io import BytesIO
from models import TwtSettings, TwtAccounts, TwtFilters
from discord import File
from discord.ext import commands
from cogs import CustomCog, AinitMixin
from util import auto_help, ack

logger = logging.getLogger(__name__)


@events.priority(-15)
def on_tweet_with_media(data):
    """
    Event triggered when the data corresponds to a tweet with a media
    """
    return "media" in data.get("entities", {})


def setup(bot):
    bot.add_cog(Twitter(bot))


def twitter_enabled():
    async def predicate(ctx):
        async with ctx.bot.Session() as session:
            _server = await db.get_twitter_settings(session, ctx.guild.id)
            return _server

    return commands.check(predicate)


class Twitter(CustomCog, AinitMixin):

    FILESIZE_MAX = 8 * 10 ** 6  # 8 MB
    URL_REGEX = r"(https?://)?(www.)?twitter.com/(\S+)/status/(\d+)(\?s=\d+)?"
    EVENT_DATE_REGEX = r"(\s+|^)(\d{6}|\d{8})\s+"

    def __init__(self, bot):
        super().__init__(bot)

        self.bot = bot
        self.feed = None
        self.stream_thing = None
        self.client = None
        self.stream_task = None
        self.session = aiohttp.ClientSession()
        self.keys = {}
        twitter_config = self.bot.config["cogs"]["twitter"]
        self.keys["consumer_key"] = twitter_config["consumer_key"]
        self.keys["consumer_secret"] = twitter_config["consumer_secret"]
        self.keys["access_token"] = twitter_config["access_token"]
        self.keys["access_token_secret"] = twitter_config["access_token_secret"]
        super(AinitMixin).__init__()

    async def _ainit(self):
        await self.bot.wait_until_ready()
        self.client = PeonyClient(**self.keys, loop=self.bot.loop)
        self.gen_accounts = list(set(await self.generate_accounts()))  # remove dupes
        logger.info(f"Loaded {len(self.gen_accounts)} twitter accounts to follow")
        if self.gen_accounts:
            self.stream_task = asyncio.create_task(self.streaming())

    async def generate_accounts(self):
        async with self.bot.Session() as session:
            accounts_list = await db.get_twitter_accounts(session)

        accounts_list = list(
            set([server.account_id for server in accounts_list])
        )  # remove dupes
        logger.info(
            f"Generated new accounts list with {len(accounts_list)} twitter accounts to follow"
        )

        return accounts_list

    async def streaming(self):
        self.feed = self.client.stream.statuses.filter.post(follow=self.gen_accounts)

        async with self.feed as stream:
            self.stream_thing = stream
            async for tweet in self.stream_thing:
                if on_tweet_with_media(tweet):
                    logger.info(
                        f"Initiating stream processing for: @{tweet.user.screen_name} - {tweet.id_str}"
                    )
                    await self.manage_twt(tweet)

    @auto_help
    @commands.group(
        name="twitter",
        aliases=["twt"],
        brief="Automatically post twitter pics to specific channels based on tags and accounts",
        invoke_without_command=True,
    )
    @commands.has_permissions(administrator=True)
    async def twitter(self, ctx):
        await ctx.send_help(self.twitter)

    @twitter.command(brief="Prints Twitter Stats")
    @commands.is_owner()
    async def stats(self, ctx):
        accts_followed = len(self.gen_accounts)
        time_start = time.time()
        await self.client.api.statuses.show.get(
            id=1230927030163628032, include_entities=False, trim_user=True
        )
        time_end = time.time()
        stats_embed = discord.Embed()
        stats_embed.set_author(name="Twitter Cog Global Stats")
        stats_embed.add_field(
            name="Number Accounts Followed", value=f"{accts_followed}", inline=False
        )
        stats_embed.add_field(
            name="Twitter API Latency",
            value=f"{(time_end-time_start)*1000}ms",
            inline=False,
        )
        await ctx.send(embed=stats_embed)

    @twitter.command(brief="Enable Twitter pic posting on server")
    @commands.has_permissions(administrator=True)
    @ack
    async def enable(self, ctx, channel: discord.TextChannel):
        """
        Enables Twitter pic posting on the server, must specify the catchall channel

        Example usage:
        `{prefix}twitter enable #ot5` or '{prefix}twitter enable #group'

        """
        async with self.bot.Session() as session:
            server_settings = await db.get_twitter_settings(session, ctx.guild.id)
            if server_settings:
                server_settings[0].default_channel = channel.id
                logger.info(
                    f"Guild {ctx.guild.name} default channel updated to {channel.name}"
                )
            else:
                server_settings = TwtSettings(
                    _guild=ctx.guild.id, default_channel=channel.id
                )
                session.add(server_settings)
                logger.info(
                    f"Guild {ctx.guild.name} enabled twitter with default channel {channel.name}"
                )
            await session.commit()

    @twitter.command(brief="Post tweet as if caught from stream")
    @commands.has_permissions(manage_messages=True)
    @ack
    async def post(self, ctx, tweet_url: commands.clean_content):
        """
        Will post individual tweet using sorting methods as implemented with hashtags by server

        Example usage:
        {prefix}twitter post https://twitter.com/Mias_Other_Half/status/1379979650605137928

        """
        tweet_urls = re.finditer(self.URL_REGEX, tweet_url)
        tweet_ids = [_tweet_url.group(4) for _tweet_url in tweet_urls]

        if tweet_ids:
            async with self.bot.Session() as session:
                for tweet_id in tweet_ids:
                    tweet = await self.get_tweet(ctx, tweet_id)
                    if tweet:
                        logger.info(
                            f"Processing for: @{tweet.user.screen_name} - {tweet.id_str} in {ctx.guild.name}"
                        )
                        server_list = [ctx.guild.id]
                        tags_list = [tag.text for tag in tweet.entities.hashtags]
                        if tags_list:
                            # remove discord's default Twitter embed
                            try:
                                await ctx.message.edit(suppress=True)
                            except discord.Forbidden:
                                pass
                            channels_list = await self.get_channels(
                                servers=server_list, tags=tags_list, session=session
                            )
                            tweet_txt, file_list = await self.create_post(tweet)
                            await self.manage_post_tweet(
                                tweet_txt, file_list, channels_list
                            )

    @twitter.group(
        name="add",
        brief="Add sorting strategies based on channels, tags, and accounts",
        invoke_without_command=True,
    )
    @twitter_enabled()
    async def add(self, ctx):
        await ctx.send_help(self.add)

    @add.command(
        name="hashtag",
        brief="Add a channel for a member's pictures or videos to be posted in",
    )
    @twitter_enabled()
    @commands.has_permissions(manage_messages=True)
    @ack
    async def add_hashtag(
        self, ctx, channel: discord.TextChannel, hashtag: commands.clean_content
    ):
        """
        Associates a hashtag with a specific channel, more than one hashtag can be associated with any channel

        Example usage:
        `{prefix}twitter add hashtag <channel> <hashtag>`
        `{prefix}twitter add hashtag #Irene 아이린`

        """
        # in case they enter it with the hashtag character
        tag_conditioned = hashtag.split("#")[-1]
        # check if hashtag already exists
        async with self.bot.Session() as session:
            twitter_filter = await db.get_twitter_filters(
                session, hashtag=tag_conditioned, guild_id=ctx.guild.id
            )
            if twitter_filter:
                twitter_filter[0].channel = channel.id
                await db.delete_twitter_filters(session, tag_conditioned, ctx.guild.id)
                logger.info(
                    f"Guild {ctx.guild.id} updated {tag_conditioned} to #{channel}"
                )
                await ctx.send(f"#{tag_conditioned} channel updated to {channel}")
            else:
                logger.info(
                    f"Guild {ctx.guild.id} added {tag_conditioned} to #{channel}"
                )

            twitter_filter = TwtFilters(
                _guild=ctx.guild.id, hashtag=tag_conditioned, _channel=channel.id
            )
            session.add(twitter_filter)
            await session.commit()

    @add.command(name="account", brief="Add a twitter account for the server to follow")
    @twitter_enabled()
    @commands.has_permissions(manage_messages=True)
    @ack
    async def add_account(self, ctx, account: commands.clean_content):
        """
        Adds a twitter account for a server to follow, to be filtered by associated tags into channels

        Example usage:
        `{prefix}twitter add account thinkB329`

        """
        # in case they enter it with the @ character
        account_conditioned = account.split("@")[-1]
        try:
            account_id = await self.client.api.users.lookup.get(
                screen_name=[account_conditioned]
            )
        except peony.exceptions.UserNotFound:
            await ctx.send(f"User {account} not found")
            return None
        except (peony.exceptions.UserSuspended, peony.exceptions.AccountSuspended):
            await ctx.send(f"User {account} is suspended")
            return None
        except peony.exceptions.AccountLocked:
            await ctx.send(f"User {account} is locked")
            return None

        if account_id:
            account_id = account_id[0]

            async with self.bot.Session() as session:
                accounts_list = await db.get_twitter_accounts(
                    session, account_id=account_id.id_str, _guild=ctx.guild.id
                )

                if accounts_list:  # check if already followed
                    pass
                else:
                    logger.info(
                        f"Guild {ctx.guild.name} added account {account_id.screen_name}"
                    )
                    new_account = TwtAccounts(
                        _guild=ctx.guild.id, account_id=account_id.id_str
                    )
                    session.add(new_account)
                    await session.commit()

            self.gen_accounts = await self.generate_accounts()
            if self.stream_task:
                self.stream_task.cancel()
            self.stream_task = asyncio.create_task(self.streaming())

    @twitter.group(
        name="remove",
        brief="Remove sorting strategies based on channels, tags, and accounts",
        invoke_without_command=True,
    )
    @twitter_enabled()
    async def remove(self, ctx):
        await ctx.send_help(self.add)

    @remove.command(
        name="hashtag",
        brief="Remove a channel for a member's pictures or videos to be posted in",
    )
    @twitter_enabled()
    @commands.has_permissions(manage_messages=True)
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
            logger.info(f"Guild {ctx.guild.id} deleted hastag {tag_conditioned}")
            await db.delete_twitter_filters(session, tag_conditioned, ctx.guild.id)
            await session.commit()

    @remove.command(
        name="account", brief="Add a twitter account for the server to follow"
    )
    @twitter_enabled()
    @commands.has_permissions(manage_messages=True)
    @ack
    async def remove_account(self, ctx, account: commands.clean_content):
        """
        Unfollows a twitter account for the server

        Example usage:
        `{prefix}twitter remove account thinkB329`

        """
        # in case they enter it with the @ character
        account_conditioned = account.split("@")[-1]
        account_id = await self.client.api.users.lookup.get(
            screen_name=[account_conditioned]
        )
        if account_id:
            account_id = account_id[0].id_str

            async with self.bot.Session() as session:
                logger.info(f"Guild {ctx.guild.id} deleted account {account_id}")
                await db.delete_accounts(session, account_id, ctx.guild.id)
                await session.commit()

            self.gen_accounts = await self.generate_accounts()
            if self.stream_task:
                self.stream_task.cancel()
            self.stream_task = asyncio.create_task(self.streaming())

    @twitter.group(
        name="show",
        brief="Show what accounts or sorting strategies currently enabled",
        invoke_without_command=True,
    )
    @twitter_enabled()
    async def show(self, ctx):
        await ctx.send_help(self.show)

    @show.command(name="accounts", brief="List all accounts followed by this server")
    @twitter_enabled()
    @commands.has_permissions(manage_messages=True)
    async def accounts(self, ctx):
        async with self.bot.Session() as session:
            accounts_followed = await db.get_twitter_accounts(
                session, _guild=ctx.guild.id
            )
        accounts_followed = [guild.account_id for guild in accounts_followed]
        accounts_embed = discord.Embed()
        accounts_embed.set_author(name="Accounts Followed")
        user_name_list = await self.client.api.users.lookup.get(
            user_id=accounts_followed
        )
        for account in user_name_list:
            accounts_embed.add_field(
                name=f"@{account.screen_name}", value=f"{account.name}"
            )
        await ctx.send(embed=accounts_embed)

    @show.command(
        name="hashtags", brief="List all hashtags and channels for this server"
    )
    @twitter_enabled()
    @commands.has_permissions(manage_messages=True)
    async def hashtags(self, ctx):
        async with self.bot.Session() as session:
            channels_list = await db.get_twitter_filters(session, guild_id=ctx.guild.id)
        hashtag_embed = discord.Embed()
        hashtag_embed.set_author(name="Hashtag to Channel Map")
        for server in channels_list:
            hashtag_embed.add_field(
                name=f"#{server.hashtag}",
                value=f"{self.bot.get_channel(server._channel).mention}",
            )
        await ctx.send(embed=hashtag_embed)

    async def manage_twt(self, tweet):
        async with self.bot.Session() as session:
            tags_list = [tag.text for tag in tweet.entities.hashtags]
            if tags_list:
                server_list = await db.get_twitter_accounts(
                    session, account_id=tweet.user.id_str
                )
                server_list = [server._guild for server in server_list]

                channels_list = await self.get_channels(
                    servers=server_list, tags=tags_list, session=session
                )
                tweet_txt, file_list = await self.create_post(tweet)
                await self.manage_post_tweet(tweet_txt, file_list, channels_list)

    async def get_tweet(self, ctx, tweet_id):
        try:
            tweet = await self.client.api.statuses.show.get(
                id=tweet_id,
                include_entities=True,
                tweet_mode="extended",
                trim_user=True,
            )
        except (peony.exceptions.StatusNotFound, peony.exceptions.HTTPNotFound):
            await ctx.send("Tweet not found")
            return None
        return tweet

    async def get_channels(self, servers, tags, session):
        servers_channels_raw = await db.get_twitter_filters(
            session, tag_list=tags, guild_list=servers
        )
        servers_dict = {server._guild: set() for server in servers_channels_raw}

        # get channels into dict per server
        for server in servers_channels_raw:
            # just one of each, so we use a set since
            # multiple hashtags can map to the same channel
            servers_dict[server._guild].add(server._channel)

        channel_list = []
        for server_id in servers_dict:
            if len(servers_dict[server_id]) > 1:
                server_settings = await db.get_twitter_settings(session, server_id)
                channel_list.append(server_settings[0].default_channel)
            else:
                channel_list.extend(servers_dict[server_id])

        return channel_list

    async def create_post(self, tweet, is_stream=True):
        KR_UTC_OFFSET = datetime.timedelta(hours=9)
        tweet_date = datetime.datetime.strptime(
            tweet.created_at, "%a %b %d %H:%M:%S %z %Y"
        )
        tweet_date = (tweet_date + KR_UTC_OFFSET).strftime("%y%m%d")

        event_date = re.search(self.EVENT_DATE_REGEX, tweet.text)
        date = event_date.group(2)[-6:] if event_date else tweet_date

        username = tweet.user.screen_name
        file_list = []

        if is_stream:
            post = f"`{date} - cr: @{username}`"
            post += f"\n<https://twitter.com/{username}/status/{tweet.id}>"
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

            async with self.session.get(video_url) as response:
                video_bytes = BytesIO(await response.read())

            video_size = video_bytes.getbuffer().nbytes
            if video_size < self.FILESIZE_MAX:
                post += f"\n<{video_url}>"
                file_list.append(File(video_bytes, filename=video_filename))
            else:
                post += f"\n{video_url}"

        else:
            for image in tweet.extended_entities.media:
                img_url_orig = f"{image.media_url}:orig"
                img_filename = image["media_url"].split("/")[-1]

                async with self.session.get(img_url_orig) as response:
                    img_bytes = BytesIO(await response.read())

                file_list.append(File(img_bytes, filename=img_filename))

                post += f"\n<{img_url_orig}>"

        return post, file_list

    async def manage_post_tweet(self, post, files, channels):
        post_list = []
        for channel in channels:
            post_list.append(self.post_tweet(post, copy.deepcopy(files), channel))
        await asyncio.gather(*post_list)

    async def post_tweet(self, post, files, channel):
        await self.bot.get_channel(channel).send(post)
        for file in files:
            await self.bot.get_channel(channel).send(file=file)

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)
        if ctx.valid or not ctx.guild or message.webhook_id or message.author.bot:
            return

        results = re.finditer(self.URL_REGEX, message.content)
        tweet_ids = [result.group(4) for result in results]

        if len(tweet_ids) > 0:
            confirm = await SimpleConfirm(message, emoji=INSPECT_EMOJI).prompt(ctx)
            if confirm:
                async with ctx.typing():
                    for tweet_id in tweet_ids:
                        tweet = await self.get_tweet(ctx, tweet_id)
                        if tweet:
                            if "extended_entities" in tweet:
                                # remove discord's default twitter embed
                                try:
                                    await ctx.message.edit(suppress=True)
                                except discord.Forbidden:
                                    pass
                                tweet_txt, file_list = await self.create_post(
                                    tweet, is_stream=False
                                )
                                await self.post_tweet(
                                    tweet_txt, file_list, ctx.channel.id
                                )
