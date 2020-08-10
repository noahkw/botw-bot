import asyncio
import logging
from io import BytesIO
import peony
from peony import events
import re
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


tags = {661348382740054036: {'soeun': 'soeun', '박소은': 'soeun', '소은': 'soeun',
                            'monday': 'monday', '먼데이': 'monday', '김지민': 'monday',
                            'soojin': 'soojin', '이수진': 'soojin', '수진': 'soojin',
                            'jiyoon': 'jiyoon', '신지윤': 'jiyoon', '지윤': 'jiyoon',
                            'jaehee': 'jaehee', '재희': 'jaehee', '이재희': 'jaehee',
                            'jihan': 'jihan', '지한': 'jihan', '한지효': 'jihan',
                            'zoa': 'zoa', '조아': 'zoa', '조혜원': 'jihan'}
        }

channels = {661348382740054036: {'soeun': {'pics': 741715615655395329, 'videos': 741828479246401657},
                                'monday': {'pics': 741828479246401657, 'videos': 741715615655395329}}
            }

accounts = {'souprknowva': '1240553343535083521',
            'dayoff2002': '1280725956798246914',
            'MUJIGAETTEOK7': '1238819537279021059',
            'Caramel021026': '1279034605522178048',
            'KIMJIMIN020510': '1282590485429645312'
            }

type_of_server = {661348382740054036: 'group'}

testing = TwitterSettings(661348382740054036, channels[661348382740054036], tags[661348382740054036],
                           accounts, type_of_server[661348382740054036])

# servers = {661348382740054036: testing}
servers = [testing]


@events.priority(-15)
def on_tweet_with_media(data):
    """
        Event triggered when the data corresponds to a tweet with a media
    """
    return 'media' in data.get('entities', {})


def setup(bot):
    bot.add_cog(Twitter(bot))


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
        self.feed = self.client.stream.statuses.filter.post(follow= await self.generate_accounts())

        async with self.feed as stream:
            async for tweet in stream:
                if on_tweet_with_media(tweet):
                    await self.manage_twt(tweet)

    async def manage_twt(self, tweet):
        servers_following = await self.get_servers(tweet.user.screen_name)
        members = await self.tag_search(servers_following, tweet.text)

        tweet_type = 'videos' if 'video_info' in tweet.extended_entities.media[0] else 'pics' 

        channel_to_post_to = await self.get_channels(servers_following, members, tweet_type)

        post = await self.create_post(tweet, tweet_type)
        await self.post_tweet(post, channel_to_post_to)

        # if len(members) == 1:
        #     channel = channels['{members[0]}']['pics']
        #     if channel:
        #         post = await self.create_post(tweet)
        #         await self.post_tweet(post, channel)
        # else:
        #     pass

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







