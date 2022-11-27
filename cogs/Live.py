import asyncio
import dataclasses
import json
import logging

import aiohttp
import discord
from aiohttp import ClientWebSocketResponse
from discord.ext import commands

from botwbot import BotwBot
from cogs import AinitMixin
from util import PrivilegedCog, auto_help

logger = logging.getLogger(__name__)


async def setup(bot: BotwBot):
    await bot.add_cog(Live(bot), guilds=await bot.get_guilds_for_cog(Live))


class WSChannel:
    args: list


@dataclasses.dataclass
class LiveUser:
    userName: str

    def __hash__(self):
        return hash(self.userName)


class LiveUsers(WSChannel):
    users: list[LiveUser]

    def __str__(self):
        return "Now live: " + ", ".join(live_user.userName for live_user in self.users)

    @staticmethod
    def parse(args):
        out = LiveUsers()
        out.users = []

        for arg in args:
            out.users.append(LiveUser(arg["userName"]))

        return out


class Subscriber:
    async def notify(self, data: WSChannel):
        pass


CHANNEL_MAP = {
    # "sendBotChannelUpdate": ChannelUpdate,
    "getliveusers": LiveUsers,
}


class SyncStreamLiveWebSocket:
    def __init__(self, ws_url: str, token: str, session: aiohttp.ClientSession):
        self.ws_url = ws_url
        self.session = session
        self.ws: ClientWebSocketResponse = None
        self.token = token
        self._ready = asyncio.Event()
        self._subscribers: dict[str, list[Subscriber]] = {}

    def subscribe(self, channel: str, subscriber: Subscriber):
        subscribers = self._subscribers.setdefault(channel, [])

        if subscriber in subscribers:
            return

        subscribers.append(subscriber)

    async def send(self, message: dict):
        raw = (json.dumps(message) + "").encode()

        await self.ws.send_bytes(raw)

    async def authenticate(self):
        await self._ready.wait()
        await self.send(
            {
                "protocol": "json",
                "version": 1,
            }
        )
        await self.send(
            {
                "target": "AuthenticateBot",
                "arguments": [self.token],
                "type": 1,
            }
        )

    async def start(self):
        async with self.session.ws_connect(self.ws_url) as ws:
            self.ws = ws
            self._ready.set()
            async for msg in ws:
                try:
                    chunks = [
                        json.loads(chunk)
                        for chunk in msg.data.split("\x1e")
                        if len(chunk) > 0
                    ]
                except Exception:
                    logger.exception("Error decoding ws msg", msg)

                for data in chunks:
                    if error := data.get("error"):
                        logger.info("Error on ws '%s'", error)

                    channel = data.get("target")
                    if channel is None:
                        continue

                    if channel_cls := CHANNEL_MAP.get(channel):
                        args = data["arguments"][0]
                        obj = channel_cls.parse(args)

                        for subscriber in self._subscribers.get(channel, []):
                            asyncio.create_task(subscriber.notify(obj))


class ChannelUpdater(Subscriber):
    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        self.live_users: set[LiveUser] = set()

    async def notify(self, data: LiveUsers):
        new_data = set(data.users)
        newly_live = new_data - self.live_users

        if len(newly_live) > 0:
            await self.channel.send(
                f"Now live: {', '.join([new_live_user.userName for new_live_user in newly_live])}"
            )

        self.live_users = new_data


class Live(PrivilegedCog, AinitMixin):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

        config = self.bot.config["cogs"]["live"]
        self.session = aiohttp.ClientSession()
        self.sync_stream_ws = SyncStreamLiveWebSocket(
            config["sync_stream_ws"], config["sync_stream_token"], self.session
        )
        self.channel_updater = ChannelUpdater(
            bot.get_channel(config["sync_stream_updates_channel"])
        )
        self.sync_stream_ws.subscribe("getliveusers", self.channel_updater)

        super(AinitMixin).__init__()

    async def _ainit(self):
        asyncio.create_task(self.sync_stream_ws.start())
        await self.sync_stream_ws.authenticate()

    @auto_help
    @commands.group(
        brief="Configure live stream updates for the server",
    )
    @commands.has_permissions(administrator=True)
    async def live(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.live)
