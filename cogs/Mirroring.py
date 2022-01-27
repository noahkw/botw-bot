import logging

from discord.ext import commands

import db
from cogs import CustomCog, AinitMixin
from models import ChannelMirror
from util import flatten, ack, auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Mirroring(bot))


class GlobalTextChannelConverter(commands.Converter):
    def __init__(self):
        self.text_channel_converter = commands.TextChannelConverter()

    async def convert(self, ctx, argument):
        try:
            return await self.text_channel_converter.convert(ctx, argument)
        except commands.BadArgument:
            # do global lookup via ID
            channel = ctx.bot.get_channel(int(argument))
            if channel is not None:
                return channel
            else:
                raise commands.BadArgument(f'Channel "{argument}" not found.')


class Mirroring(CustomCog, AinitMixin):
    def __init__(self, bot):
        super().__init__(bot)
        self.mirrors = {}

        ChannelMirror.inject_bot(self.bot)

        super(AinitMixin).__init__()

    async def _ainit(self):
        await self.bot.wait_until_ready()

        async with self.bot.Session() as session:
            _mirrors = await db.get_mirrors(session)

            for mirror in _mirrors:
                valid = await mirror.sanity_check(session)
                if valid:  # ignore mirrors that we can't access anymore
                    self.append_mirror(mirror)

            await session.commit()

        logger.info(f"# Initial mirrors from db: {len(self.mirrors)}")

    @auto_help
    @commands.group(brief="Create channel mirrors between servers")
    @commands.is_owner()
    async def mirror(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send_help(self.mirror)

    def append_mirror(self, mirror):
        origin_mirrors = self.mirrors.setdefault(mirror._origin, [])
        origin_mirrors.append(mirror)

    @mirror.command()
    async def add(
        self,
        ctx,
        origin: GlobalTextChannelConverter,
        destination: GlobalTextChannelConverter,
    ):
        if origin == destination:
            raise commands.BadArgument("Cannot mirror a channel to itself.")
        elif destination.id in self.mirrors and origin.id in [
            mirror._destination for mirror in self.mirrors[destination.id]
        ]:
            raise commands.BadArgument("This would create a circular mirror.")

        async with self.bot.Session(expire_on_commit=False) as session:
            mirror = ChannelMirror(
                _origin=origin.id,
                _destination=destination.id,
            )

            if mirror in flatten(self.mirrors.values()):
                raise commands.BadArgument("This mirror already exists.")

            dest_webhook = await destination.create_webhook(
                name=f"Mirror from {origin}@{origin.guild}"
            )
            mirror.webhook = dest_webhook

            session.add(mirror)
            await session.commit()

            self.append_mirror(mirror)
            await ctx.send(f"Added {mirror}")

    @mirror.command(aliases=["delete"])
    @ack
    async def remove(
        self,
        ctx,
        origin: GlobalTextChannelConverter,
        destination: GlobalTextChannelConverter,
    ):
        try:
            mirrors = self.mirrors[origin.id]
            mirror = [m for m in mirrors if m._destination == destination.id].pop()
        except IndexError:
            raise commands.BadArgument("This mirror does not exist.")
        except KeyError:
            raise commands.BadArgument(f"Channel {origin.mention} has no mirrors.")

        if webhook := (await mirror.webhook):
            await webhook.delete()

        mirrors.remove(mirror)

        async with self.bot.Session(expire_on_commit=False) as session:
            session.delete(mirror)
            await session.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)

        if ctx.valid or message.channel.id not in self.mirrors:
            return

        mirrors = self.mirrors[message.channel.id]
        for mirror in mirrors:
            if not mirror.enabled:
                continue

            author = message.author
            files = [await attachment.to_file() for attachment in message.attachments]
            webhook = await mirror.webhook
            await webhook.send(
                message.clean_content,
                username=author.name,
                avatar_url=author.avatar.url,
                files=files,
            )
