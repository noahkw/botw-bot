import asyncio
import logging
from io import BytesIO
import peony
from peony import events
import re
import discord
from discord import File
from discord.ext import commands
from cogs import CustomCog, AinitMixin

from util import auto_help

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
        


# tags = {661348382740054036: {'soeun': 'soeun', '박소은': 'soeun', '소은': 'soeun',
#                             'monday': 'monday', '먼데이': 'monday', '김지민': 'monday',
#                             'soojin': 'soojin', '이수진': 'soojin', '수진': 'soojin',
#                             'jiyoon': 'jiyoon', '신지윤': 'jiyoon', '지윤': 'jiyoon',
#                             'jaehee': 'jaehee', '재희': 'jaehee', '이재희': 'jaehee',
#                             'jihan': 'jihan', '지한': 'jihan', '한지효': 'jihan',
#                             'zoa': 'zoa', '조아': 'zoa', '조혜원': 'jihan'}
#         }

tags = {}

channels = {661348382740054036: {'soeun': {'pics': 741715615655395329, 'videos': 741828479246401657},
                                'monday': {'pics': 741828479246401657, 'videos': 741715615655395329}}
            }
channels = {}
# accounts = {'souprknowva': '1240553343535083521',
            # 'dayoff2002': '1280725956798246914',
            # 'MUJIGAETTEOK7': '1238819537279021059',
            # 'Caramel021026': '1279034605522178048',
            # 'KIMJIMIN020510': '1282590485429645312'
            # }
accounts = {}
# type_of_server = {661348382740054036: 'group'}
type_of_server = {}
# testing = TwitterSettings(661348382740054036, channels[661348382740054036], tags[661348382740054036],
#                            accounts, type_of_server[661348382740054036])

# servers = {661348382740054036: testing}
servers = {}
enabled_servers = set();


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
        logger.info(f'# Initial twitter accounts followed from db: {len(accounts.values())}')
        super(AinitMixin).__init__()        

    async def _ainit(self):
        await self.bot.wait_until_ready()
        self.client = peony.PeonyClient(**keys, loop=self.bot.loop)
        # await self.generate_accounts();
        await self.stream()

    async def generate_accounts(self):
        accounts = []
        for server in servers:
            accounts.extend(list(server.followed_accounts.values()))
        return accounts

    async def stream(self):
        gen_accounts = await self.generate_accounts()
        gen_accounts = list(set(gen_accounts)) # remove dupes
        if gen_accounts:
            self.feed = self.client.stream.statuses.filter.post(follow= gen_accounts)

            async with self.feed as stream:
                async for tweet in stream:
                    if on_tweet_with_media(tweet):
                        await self.manage_twt(tweet)


    @auto_help
    @commands.group(name='twitter', aliases=['twt'], brief='Automatically post twitter pics to specific channels based on tags and accounts',
                    invoke_without_command=True)
    # @commands.has_permissions(administrator=True)
    async def twitter(self, ctx):
        await ctx.send_help(self.twitter)

    @twitter.command(brief='Enable Twitter pic posting on server')
    # @commands.has_permissions(administrator=True)
    async def enable(self, ctx, type_of_server):
        """
        Enables Twitter pic posting on the server, must specify the type of server
        either "group" or the name of the meber if a member server

        Example usage:
        `{prefix}twitter enable group` or '{prefix}twitter enable irene'

        """
        if not type_of_server:
            await ctx.send('Please supply a type of server value')
            return

        if ctx.guild.id in enabled_servers:
            await ctx.send('server already enabled for Twitter picture posting')
        else:
            enabled_servers.add(guild.id)
            servers[guild.id] = TwitterSettings(guild=guild.id, channels={}, tags={}, followed_accounts={}, server_type=type_of_server)

    @twitter.group(name='add', brief='Add sorting strategies based on channels, tags, and accounts')
    async def add(self, ctx):
        await ctx.send_help(self.add)

    @add.command(name='channel', brief='Add a channel for a member\'s pictures or videos to be posted in')
    @twitter_enabled()
    # @commands.has_permissions(administrator=True)
    async def add_channel(self, ctx, type_of_channel: commands.clean_content, channel: discord.TextChannel, name: commands.clean_content):
        """
        Associates a member with a specific channel to have their pictures or videos posted in.
        Available channel types are pics or videos

        Example usage:
        `{prefix}twitter add channel pics #Irene irene`

        """
        if type_of_channel.lower() != 'pics' or 'video':
            await ctx.send('Please enter a valid channel type "pics" or "videos"')
            return
        
        servers[ctx.guild.id].channels.setdefault(name, {})[type_of_channel] = channel.id


    @add.command(name='tag', brief='Add a tag for a member\'s pictures or videos to be filtered with')
    @twitter_enabled()
    # @commands.has_permissions(administrator=True)
    async def add_tag(self, ctx, member: commands.clean_content, tag: commands.clean_content):
        """
        Associates a hashtag with a member to filter tweets into their specified channels.

        Example usage:
        `{prefix}twitter add tag #Irene irene` or '{prefix}twitter add tag #배주현 irene'

        """
        if not member or not tag:
            await ctx.send('Please enter both a hashtag and a member, see help for example usage')
            return
        tag_conditioned = tag.split('#')[-1] # in case they enter it with the hashtag character
        servers[ctx.guild.id].tags[tag_conditioned] = member

    @add.command(name='account', brief='Add a twitter account for the server to follow')
    @twitter_enabled()
    # @commands.has_permissions(administrator=True)
    async def add_account(self, ctx, account: commands.clean_content):
        """
        Adds a twitter account for a server to follow, to be filtered by associated tags and members into channels

        Example usage:
        `{prefix}twitter add account thinkB329`

        """
        if not account:
            await ctx.send('Please enter an account to follow')
            return
        account_conditioned = account.split('@')[-1] # in case they enter it with the @ character
        account_id = self.client.api.lookup_users(screen_names=[account_conditioned])
        servers[ctx.guild.id].followed_accounts[account_conditioned] = account_id

        await self.generate_accounts()
        await self.feed.disconnect()
        await self.stream()


    async def manage_twt(self, tweet):
        servers_following = await self.get_servers(tweet.user.screen_name)
        members = await self.tag_search(servers_following, tweet.text)
        tweet_type = 'videos' if 'video_info' in tweet.extended_entities.media[0] else 'pics' 
        channel_to_post_to = await self.get_channels(servers_following, members, tweet_type)
        post = await self.create_post(tweet, tweet_type)
        await self.post_tweet(post, channel_to_post_to)

    async def get_servers(self, account):
        results = []
        for server in servers:
            if account in server.followed_accounts:
                results.append(server)
        return results


    async def tag_search(self, servers, text):
        re_twt_tag = re.compile('#\S+') # Regex to find all hashtags in tweet
        re_twt_tags = re_twt_tag.findall(text)
        results = {}
        for hashtag in re_twt_tags:
            for server in servers:
                server_results = set()
                hits = server.tags.get(hashtag[1::].lower(), None) #compare hashtags without # sign against known tags
                if hits:
                    # if server in results:
                    #     results[server].add(hits)
                    # else:
                    #     results[server] = set(hits)
                    results.setdefault(server, set()).add(hits)
        return results


    async def get_channels(self, servers, members_list, tweet_type):
        channels_list = []
        for server in servers:
            print(members_list[server])
            print(tweet_type)
            if server.server_type == 'group' and len(members_list[server]) > 1:
                if 'group' in server.channels:
                    channels_list.append(server.channels['group'][tweet_type])
                else:
                    for members in members_list[server]:
                        if members in server.channels:
                            channels_list.append(server.channels[members][tweet_type])
            elif server.server_type != 'group' and len(members_list[server]) > 1:
                if server.server_type in members_list[server]:
                    channels_list.append(server.channels[server.server_type][tweet_type])
            else:
                for members in members_list[server]:
                    if members in server.channels:
                        channels_list.append(server.channels[members][tweet_type])
        return channels_list

    async def create_post(self, tweet, tweet_type):
        tweet_date=str(tweet.created_at)
        tweet_date= f'{tweet_date[2:4]}{tweet_date[5:7]}{tweet_date[8:10]}'


        date_6=re.compile('\d\d\d\d\d\d')
        date_8=re.compile('\d\d\d\d\d\d\d\d')
        date_6_result=date_6.match(tweet.text)
        date_8_result=date_8.match(tweet.text)

        if date_6_result:
            date=date_6_result.group()
        elif date_8_result:
            date=date_8_result.group()[-5]
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
        # channel_to_post_to
        for channel in channels:
            await self.bot.get_channel(channel).send(post)







