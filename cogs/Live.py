import asyncio
import dataclasses
import json
import logging

import aiohttp
import aiohttp.client_exceptions
import discord
from aiohttp import ClientWebSocketResponse
from discord.ext import commands
from cachetools import TTLCache

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


class WebSocketClosure(Exception):
    pass


class SyncStreamLiveWebSocket:
    def __init__(self, ws_url: str, token: str, session: aiohttp.ClientSession):
        self.ws_url = ws_url
        self.session = session
        self.ws: ClientWebSocketResponse = None
        self.token = token
        self._ready = asyncio.Event()
        self._subscribers: dict[str, list[Subscriber]] = {}
        self._msg_timeout = 20  # 20s, keepalive from the server every 15s
        self._reconnect_tries = 0

    def subscribe(self, channel: str, subscriber: Subscriber):
        subscribers = self._subscribers.setdefault(channel, [])

        if subscriber in subscribers:
            return

        subscribers.append(subscriber)

    async def send(self, message: dict):
        raw = (json.dumps(message) + "").encode()

        await self.ws.send_bytes(raw)

    async def authenticate(self):
        await self.send(
            {
                "target": "AuthenticateBot",
                "arguments": [self.token],
                "type": 1,
            }
        )

    async def negotiate(self):
        await self.send(
            {
                "protocol": "json",
                "version": 1,
            }
        )

    async def start(self):
        while True:
            try:
                await self.connect_ws()
            except WebSocketClosure:
                wait = self._msg_timeout * self._reconnect_tries
                logger.info(
                    "Reconnecting SyncStreamLiveWebSocket after closure in %d seconds (%d tries)",
                    wait,
                    self._reconnect_tries,
                )

                self._reconnect_tries += 1

                await asyncio.sleep(wait)

    async def connect_ws(self):
        try:
            async with self.session.ws_connect(self.ws_url) as ws:
                self.ws = ws
                self._ready.set()
                self._reconnect_tries = 0

                await self.negotiate()
                await self.authenticate()

                while True:
                    try:
                        msg = await ws.receive(timeout=self._msg_timeout)

                        if msg.type is aiohttp.WSMsgType.ERROR:
                            logger.exception("Received websocket error %s", msg)
                        elif msg.type in (
                            aiohttp.WSMsgType.BINARY,
                            aiohttp.WSMsgType.TEXT,
                        ):
                            logger.debug("Received binary/text '%s', decoding", msg)
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.CLOSING,
                        ):
                            raise WebSocketClosure
                    except (asyncio.TimeoutError, WebSocketClosure):
                        raise WebSocketClosure

                    try:
                        chunks = [
                            json.loads(chunk)
                            for chunk in msg.data.split("\x1e")
                            if len(chunk) > 0
                        ]
                    except Exception:
                        logger.exception("Error decoding ws msg: '%s'", msg)

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
        except aiohttp.client_exceptions.ClientConnectionError:
            raise WebSocketClosure


class ChannelUpdater(Subscriber):
    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        # TTL of 15 minutes
        self.live_users: TTLCache = TTLCache(maxsize=128, ttl=15 * 60)

    async def notify(self, data: LiveUsers):
        newly_live = []

        for user in data.users:
            if user not in self.live_users:
                newly_live.append(user)

            self.live_users[user] = True

        if len(newly_live) > 0:
            await self.channel.send(
                f"Now live: {', '.join([new_live_user.userName for new_live_user in newly_live])}"
            )


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

    @auto_help
    @commands.group(
        brief="Configure live stream updates for the server",
    )
    @commands.has_permissions(administrator=True)
    async def live(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.live)
