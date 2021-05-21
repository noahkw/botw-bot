import asyncio
import logging
import peony
import requests
import aiohttp
import datetime
from peony import EventStream, PeonyClient, event_handler, events
import re
import discord
import db
import copy
from const import INSPECT_EMOJI
from menu import SimpleConfirm
from io import BytesIO
from models import twt_settings, twt_accounts, twt_filters
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
    return 'media' in data.get('entities', {})

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

    def __init__(self, bot):
        super().__init__(bot)
        
        self.bot = bot
        self.feed = None
        self.stream_thing = None
        self.client = None
        self.stream_task = None
        self.session = aiohttp.ClientSession()
        self.keys = {}
        self.keys['consumer_key'] = self.bot.config["cogs"]['twitter']['consumer_key']
        self.keys['consumer_secret'] = self.bot.config["cogs"]['twitter']['consumer_secret']
        self.keys['access_token'] = self.bot.config["cogs"]['twitter']['access_token']
        self.keys['access_token_secret'] = self.bot.config["cogs"]['twitter']['access_token_secret']
        super(AinitMixin).__init__()

    async def _ainit(self):
        await self.bot.wait_until_ready()
        self.client = PeonyClient(**self.keys, loop=self.bot.loop)
        self.gen_accounts = list(set(await self.generate_accounts())) # remove dupes
        logger.info(f"Loaded {len(self.gen_accounts)} twitter accounts to follow")
        if self.gen_accounts:
            self.stream_task = asyncio.create_task(self.streaming())

    async def generate_accounts(self):
        async with self.bot.Session() as session:
            accounts_list = await db.get_twitter_accounts(session)

        accounts_list = list(set([server.account_id for server in accounts_list])) #remove dupes
        logger.info(f"Generated new accounts list with {len(accounts_list)} twitter accounts to follow")
        
        return accounts_list

    async def streaming(self):
        self.feed = self.client.stream.statuses.filter.post(follow=self.gen_accounts)

        async with self.feed as stream:
            self.stream_thing = stream
            async for tweet in self.stream_thing:
                if on_tweet_with_media(tweet):
                    logger.info(f"Initiating stream processing for: @{tweet.user.id_str} - {tweet.id_str}")
                    await self.manage_twt(tweet)


    @auto_help
    @commands.group(name='twitter', aliases=['twt'], brief='Automatically post twitter pics to specific channels based on tags and accounts',
                    invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def twitter(self, ctx):
        await ctx.send_help(self.twitter)

    @twitter.command(brief='Enable Twitter pic posting on server')
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
                logger.info(f"Guild {ctx.guild.id} default channel updated to {channel.id}")
            else:
                server_settings = twt_settings(_guild=ctx.guild.id, default_channel=channel.id)
                session.add(server_settings)
                logger.info(f"Guild {ctx.guild.id} enabled twitter with default channel {channel.id}")
            await session.commit()


    @twitter.command(brief='Post tweet as if caught from stream')
    # @commands.has_permissions(administrator=True)
    @ack
    async def post(self, ctx, tweet_url: commands.clean_content):
        """
        Will post individual tweet using sorting methods as implemented with hashtags by server

        Example usage:
        `{prefix}twitter post https://twitter.com/Mias_Other_Half/status/1379979650605137928'

        """
        tweet_urls = re.finditer(self.URL_REGEX, tweet_url)
        tweet_ids = [_tweet_url.group(4) for _tweet_url in tweet_urls]

        if tweet_ids:
            # remove discord's default instagram embed
            try:
                await ctx.message.edit(suppress=True)
            except discord.Forbidden:
                pass

            async with self.bot.Session() as session:
                for tweet_id in tweet_ids:
                    tweet = await self.client.api.statuses.show.get(id=tweet_id, include_entities=True, tweet_mode="extended")            
                    logger.info(f"Initiating manual processing for: @{tweet.user.id_str} - {tweet.id_str} in Guild {ctx.guild.id}")
                    server_list = [ctx.guild.id]
                    tags_list = [tag.text for tag in tweet.entities.hashtags]
                    channels_list = await self.get_channels(servers=server_list, tags=tags_list, session=session)
                    tweet_txt, file_list = await self.create_post(tweet)
                    await self.post_tweet(tweet_txt, file_list, channels_list)            


    @twitter.group(name='add', brief='Add sorting strategies based on channels, tags, and accounts',
                    invoke_without_command=True)
    @twitter_enabled()
    async def add(self, ctx):
        await ctx.send_help(self.add)

    @add.command(name='hashtag', brief='Add a channel for a member\'s pictures or videos to be posted in')
    @twitter_enabled()
    # @commands.has_permissions(administrator=True)
    @ack
    async def add_hashtag(self, ctx, channel: discord.TextChannel, hashtag: commands.clean_content):
        """
        Associates a hashtag with a specific channel, more than one hashtag can be associated with any channel

        Example usage:
        `{prefix}twitter add hashtag <channel> <hashtag>`
        `{prefix}twitter add hashtag #Irene 아이린`

        """
        tag_conditioned = hashtag.split('#')[-1] # in case they enter it with the hashtag character
        #check if hashtag already exists
        async with self.bot.Session() as session:
            twitter_filter = await db.get_twitter_filters(session, hashtag=tag_conditioned, guild_id=ctx.guild.id)
            if twitter_filter:
                twitter_filter[0].channel = channel.id
                await db.delete_twitter_filters(session, tag_conditioned, ctx.guild.id)
                logger.info(f"Guild {ctx.guild.id} updated hastag {tag_conditioned} to channel {channel}")
                await ctx.send(f'#{tag_conditioned} channel updated to {channel}')
            else:
                logger.info(f"Guild {ctx.guild.id} added hastag {tag_conditioned} to channel {channel}")
                
            twitter_filter = twt_filters(_guild=ctx.guild.id, hashtag=tag_conditioned, _channel=channel.id)
            session.add(twitter_filter)  
            await session.commit()


    @add.command(name='account', brief='Add a twitter account for the server to follow')
    @twitter_enabled()
    # @commands.has_permissions(administrator=True)
    @ack
    async def add_account(self, ctx, account: commands.clean_content):
        """
        Adds a twitter account for a server to follow, to be filtered by associated tags into channels

        Example usage:
        `{prefix}twitter add account thinkB329`

        """
        account_conditioned = account.split('@')[-1] # in case they enter it with the @ character
        account_id = await self.client.api.users.lookup.get(screen_name=[account_conditioned])
        if account_id:
            account_id = account_id[0].id_str


            async with self.bot.Session() as session:
                accounts_list = await db.get_twitter_accounts(session, account_id=account_id, _guild=ctx.guild.id)

                if accounts_list: #check if already followed
                    pass
                else:
                    logger.info(f"Guild {ctx.guild.id} added account {account_id}")
                    new_account = twt_accounts(_guild=ctx.guild.id, account_id=account_id)
                    session.add(new_account)
                    await session.commit()

            self.gen_accounts = await self.generate_accounts()
            if self.stream_task:
                self.stream_task.cancel()
            self.stream_task = asyncio.create_task(self.streaming())



    @twitter.group(name='remove', brief='Remove sorting strategies based on channels, tags, and accounts',
                    invoke_without_command=True)
    @twitter_enabled()
    async def remove(self, ctx):
        await ctx.send_help(self.add)

    @remove.command(name='hashtag', brief="Remove a channel for a member's pictures or videos to be posted in")
    @twitter_enabled()
    # @commands.has_permissions(administrator=True)
    @ack
    async def remove_hashtag(self, ctx, hashtag: commands.clean_content):
        """
        Removes a hashtag

        Example usage:
        `{prefix}twitter remove 아이린`

        """
        tag_conditioned = hashtag.split('#')[-1] # in case they enter it with the hashtag character
        async with self.bot.Session() as session:
            logger.info(f"Guild {ctx.guild.id} deleted hastag {tag_conditioned}")
            await db.delete_twitter_filters(session, tag_conditioned, ctx.guild.id)
            
            await session.commit()


    @remove.command(name='account', brief='Add a twitter account for the server to follow')
    @twitter_enabled()
    # @commands.has_permissions(administrator=True)
    @ack
    async def remove_account(self, ctx, account: commands.clean_content):
        """
        Unfollows a twitter account for the server

        Example usage:
        `{prefix}twitter remove account thinkB329`

        """
        account_conditioned = account.split('@')[-1] # in case they enter it with the @ character
        account_id = await self.client.api.users.lookup.get(screen_name=[account_conditioned])
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



    async def manage_twt(self, tweet):

        async with self.bot.Session() as session:
            server_list = await db.get_twitter_accounts(session, account_id=tweet.user.id_str)
            server_list = [server._guild for server in server_list]
            tags_list = [tag.text for tag in tweet.entities.hashtags]
            channels_list = await self.get_channels(servers=server_list, tags=tags_list, session=session)
            tweet_txt, file_list = await self.create_post(tweet)
            await self.post_tweet(tweet_txt, file_list, channels_list)


    async def get_channels(self, servers, tags, session):
        servers_channels_raw = await db.get_twitter_filters(session, tag_list=tags, guild_list=servers)
        servers_dict = {server._guild : set() for server in servers_channels_raw}

        #get channels into dict per server
        for server in servers_channels_raw:
            servers_dict[server._guild].add(server._channel) #just one of each, so we use a set, since multiple hashtags can map to same channel

        channel_list = []
        for server_id in servers_dict:
            if len(servers_dict[server_id]) > 1:
                server_settings = await db.get_twitter_settings(session, server_id)
                channel_list.append(server_settings[0].default_channel)
            else:
                channel_list.extend(servers_dict[server_id])

        return channel_list


    async def create_post(self, tweet, is_stream=True):
        tweet_date  = datetime.datetime.strptime(tweet.created_at, "%a %b %d %H:%M:%S %z %Y").strftime("%y%m%d")
        date_re     = re.compile('(\s+|^)(\d{6}|\d{8})\s+')
        date_result = date_re.match(tweet.text)

        if date_result:
            date=date_result.group(2)[-6:]
        else:
            date=tweet_date

        username=tweet.user.screen_name
        url_list = []
        file_list = []

        if is_stream:
            post = f'`{date} - cr: @{username}`'
            post += f'\n<https://twitter.com/{username}/status/{tweet.id}>'
        else:
            post = ''

        if "video_info" in tweet.extended_entities.media[0]:
            if tweet.extended_entities.media[0].video_info.variants[-1].content_type == 'video/mp4':
                video_url=tweet.extended_entities.media[0].video_info.variants[-1].url
            else:
                video_url=tweet.extended_entities.media[0].video_info.variants[-2].url
            video_filename = video_url.split('/')[-1].split('?')[0]

            async with self.session.get(video_url) as response:
                video_bytes = BytesIO(await response.read())
            
            video_size = video_bytes.getbuffer().nbytes
            if video_size < self.FILESIZE_MAX:
                post+=f'\n<{video_url}>'
                file_list.append(File(video_bytes, filename=video_filename))
            else:
                post+=f'\n{video_url}'   

        else:
            for image in tweet.extended_entities.media:
                img_url_orig=f"{image.media_url}:orig"
                img_filename=image['media_url'].split('/')[-1]

                async with self.session.get(img_url_orig) as response:
                    img_bytes = BytesIO(await response.read())
                
                file_list.append(File(img_bytes, filename=img_filename))

                post+=f'\n<{img_url_orig}>'

        return post, file_list


    async def post_tweet(self, post, files, channels): 
        for channel in channels:
            files_copy = copy.deepcopy(files)
            await self.bot.get_channel(channel).send(post)
            for file in files_copy:
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
                # remove discord's default instagram embed
                try:
                    await ctx.message.edit(suppress=True)
                except discord.Forbidden:
                    pass
                async with ctx.typing():
                    for tweet_id in tweet_ids:
                        try:
                            tweet = await self.client.api.statuses.show.get(id=tweet_id, include_entities=True, tweet_mode="extended")
                            tweet_txt, file_list = await self.create_post(tweet, is_stream=False)
                            await self.post_tweet(tweet_txt, file_list, [ctx.channel.id])
                        except commands.BadArgument as error:
                            await ctx.send(error)