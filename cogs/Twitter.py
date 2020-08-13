import asyncio
import logging
import peony
from peony import EventStream, PeonyClient, event_handler, events
import re
import discord
from discord import File
from discord.ext import commands
from cogs import CustomCog, AinitMixin
from util import auto_help, ack

logger = logging.getLogger(__name__)

class TwitterSettings():
    guild: int
    channels: dict
    tags: dict
    followed_accounts: dict
    server_type: str
    def __init__(self, guild, channels, tags, followed_accounts, server_type):
        self.guild = guild
        self.channels = channels
        self.tags = tags
        self.followed_accounts = followed_accounts
        self.server_type = server_type
        
servers = {}
enabled_servers = set()

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
        return ctx.guild.id in enabled_servers

    return commands.check(predicate)


class Twitter(CustomCog, AinitMixin):

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.feed = None
        self.stream_thing = None
        self.client = None
        self.stream_task = None
        self.keys = {}
        self.keys['consumer_key'] = self.bot.config['twitter']['consumer_key']
        self.keys['consumer_secret'] = self.bot.config['twitter']['consumer_secret']
        self.keys['access_token'] = self.bot.config['twitter']['access_token']
        self.keys['access_token_secret'] = self.bot.config['twitter']['access_token_secret']
        super(AinitMixin).__init__()

    async def _ainit(self):
        await self.bot.wait_until_ready()
        self.client = peony.PeonyClient(**self.keys, loop=self.bot.loop)
        self.gen_accounts = list(set(await self.generate_accounts())) # remove dupes
        if self.gen_accounts:
            self.stream_task = asyncio.create_task(self.streaming())

    async def generate_accounts(self):
        accounts_list = []
        for server_id, server in servers.items():
            print()
            accounts_list.extend(list(server.followed_accounts.values()))
        return accounts_list

    async def streaming(self):
        self.feed = self.client.stream.statuses.filter.post(follow= self.gen_accounts)

        async with self.feed as stream:
            self.stream_thing = stream
            async for tweet in self.stream_thing:
                if on_tweet_with_media(tweet):
                    await self.manage_twt(tweet)


    @auto_help
    @commands.group(name='twitter', aliases=['twt'], brief='Automatically post twitter pics to specific channels based on tags and accounts',
                    invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def twitter(self, ctx):
        await ctx.send_help(self.twitter)

    @twitter.command(brief='Enable Twitter pic posting on server')
    # @commands.has_permissions(administrator=True)
    @ack
    async def enable(self, ctx, type_of_server):
        """
        Enables Twitter pic posting on the server, must specify the type of server
        either "group" or the name of the meber if a member server

        Example usage:
        `{prefix}twitter enable group` or '{prefix}twitter enable irene'

        """
        if ctx.guild.id in enabled_servers:
            await ctx.send('server already enabled for Twitter picture posting')
        else:
            enabled_servers.add(ctx.guild.id)
            servers[ctx.guild.id] = TwitterSettings(guild=ctx.guild.id, channels={}, tags={}, followed_accounts={}, server_type=type_of_server)

    @twitter.group(name='add', brief='Add sorting strategies based on channels, tags, and accounts',
                    invoke_without_command=True)
    @twitter_enabled()
    async def add(self, ctx):
        await ctx.send_help(self.add)

    @add.command(name='channel', brief='Add a channel for a member\'s pictures or videos to be posted in')
    @twitter_enabled()
    # @commands.has_permissions(administrator=True)
    @ack
    async def add_channel(self, ctx, type_of_channel: commands.clean_content, channel: discord.TextChannel, name: commands.clean_content):
        """
        Associates a member with a specific channel to have their pictures or videos posted in.
        Available channel types are pics or videos

        Example usage:
        `{prefix}twitter add channel pics #Irene irene`

        """
        type_of_channel = type_of_channel.lower()
        if type_of_channel not in ['pics', 'video']:
            await ctx.send('Please enter a valid channel type "pics" or "videos"')
            return
        
        servers[ctx.guild.id].channels.setdefault(name, {})[type_of_channel] = channel.id


    @add.command(name='tag', brief='Add a tag for a member\'s pictures or videos to be filtered with')
    @twitter_enabled()
    # @commands.has_permissions(administrator=True)
    @ack
    async def add_tag(self, ctx, tag: commands.clean_content, member: commands.clean_content):
        """
        Associates a hashtag with a member to filter tweets into their specified channels.

        Example usage:
        `{prefix}twitter add tag #Irene irene` or '{prefix}twitter add tag #배주현 irene'

        """
        tag_conditioned = tag.split('#')[-1] # in case they enter it with the hashtag character
        servers[ctx.guild.id].tags[tag_conditioned] = member

    @add.command(name='account', brief='Add a twitter account for the server to follow')
    @twitter_enabled()
    # @commands.has_permissions(administrator=True)
    @ack
    async def add_account(self, ctx, account: commands.clean_content):
        """
        Adds a twitter account for a server to follow, to be filtered by associated tags and members into channels

        Example usage:
        `{prefix}twitter add account thinkB329`

        """
        account_conditioned = account.split('@')[-1] # in case they enter it with the @ character
        account_id = await self.client.api.users.lookup.get(screen_name=[account_conditioned])
        servers[ctx.guild.id].followed_accounts[account_conditioned] = account_id[0].id

        self.gen_accounts = list(set(await self.generate_accounts()))
        if self.stream_task:
            self.stream_task.cancel()
        self.stream_task = asyncio.create_task(self.streaming())


    async def manage_twt(self, tweet):
        servers_following = await self.get_servers(tweet.user.screen_name)
        members = await self.tag_search(servers_following, tweet.text)
        tweet_type = 'videos' if 'video_info' in tweet.extended_entities.media[0] else 'pics'
        channel_to_post_to = await self.get_channels(servers_following, members, tweet_type)
        post = await self.create_post(tweet, tweet_type)
        await self.post_tweet(post, channel_to_post_to)

    async def get_servers(self, account):
        server_results = []
        for server_id, server in servers.items():
            if account in server.followed_accounts:
                server_results.append(server)
        return server_results


    async def tag_search(self, servers_list, text):
        re_twt_tag = re.compile('#\S+') # Regex to find all hashtags in tweet
        re_twt_tags = re_twt_tag.findall(text)
        tag_results = {}
        for hashtag in re_twt_tags:
            for server in servers_list:
                hits = server.tags.get(hashtag[1::].lower(), None) #compare hashtags without # sign against known tags
                if hits:
                    tag_results.setdefault(server.guild, set()).add(hits)
        return tag_results


    async def get_channels(self, servers, members_list, tweet_type):
        channels_list = []
        for server in servers:
            if server.server_type == 'group' and len(members_list[server.guild]) > 1:
                if 'group' in server.channels:
                    channels_list.append(server.channels['group'][tweet_type])
                else:
                    for members in members_list[server.guild]:
                        if members in server.channels:
                            channels_list.append(server.channels[members][tweet_type])
            elif server.server_type != 'group' and len(members_list[server.guild]) > 1:
                if server.server_type in members_list[server.guild]:
                    channels_list.append(server.channels[server.server_type][tweet_type])
            else:
                for members in members_list[server.guild]:
                    if members in server.channels:
                        channels_list.append(server.channels[members][tweet_type])
        return channels_list

    async def create_post(self, tweet, tweet_type):
        tweet_date=str(tweet.created_at)
        tweet_date= f'{tweet_date[2:4]}{tweet_date[5:7]}{tweet_date[8:10]}'


        # date_6=re.compile('\d\d\d\d\d\d')
        # date_8=re.compile('\d\d\d\d\d\d\d\d')
        # date_6_result=date_6.match(tweet.text)
        # date_8_result=date_8.match(tweet.text)

        date_re=re.compile('(\s+|^)(\d{6}|\d{8})\s+')
        date_result=date_re.match(tweet.text)

        # if date_6_result:
        #     date=date_6_result.group()
        # elif date_8_result:
        #     date=date_8_result.group()[-5]
        if date_result:
            date=date_result.group(2)
        else:
            date=tweet_date

        username=tweet.user.screen_name

        post=f'`{date} - cr: @{username}`'
        post+=f'\n<https://twitter.com/{username}/status/{tweet.id}>'

        if tweet_type == 'videos':
            if tweet.extended_entities.media[0].video_info.variants[-1].content_type == 'video/mp4':
                video_url=tweet.extended_entities.media[0].video_info.variants[-1].url
            else:
                video_url=tweet.extended_entities.media[0].video_info.variants[-2].url
            # video_file=video_url.split('/')[-1].split('?')[0]
            post+=f'\n{video_url}'
        else:
            for image in tweet.extended_entities.media:
                # img_url=image.media_url
                img_url_orig=f"{image.media_url}:orig"
                # img_file=image['media_url'].split('/')[-1]
                # urllib.request.urlretrieve(img_url_orig, img_file)
                post+=f'\n{img_url_orig}'

        return post

    async def post_tweet(self, post, channels):
        print(channels)
        print(post)
        for channel in channels:
            await self.bot.get_channel(channel).send(post)

