import logging

from discord.ext import commands

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

        super(AinitMixin).__init__()

    async def _ainit(self):
        await self.bot.wait_until_ready()

        query = "SELECT * FROM mirrors;"
        _mirrors = await self.bot.db.pool.fetch(query)

        for _mirror in _mirrors:
            mirror = await ChannelMirror.from_record(_mirror, self.bot)
            self.append_mirror(mirror)

        logger.info(f'# Initial mirrors from db: {len(self.mirrors)}')

    @auto_help
    @commands.group(brief='Create channel mirrors between servers')
    @commands.is_owner()
    async def mirror(self, ctx):
        pass

    def append_mirror(self, mirror):
        origin_mirrors = self.mirrors.setdefault(mirror.origin.id, [])
        origin_mirrors.append(mirror)

    @mirror.command()
    async def add(self, ctx, origin: GlobalTextChannelConverter, dest: GlobalTextChannelConverter):
        if origin == dest:
            raise commands.BadArgument('Cannot mirror a channel to itself.')
        elif dest.id in self.mirrors and origin.id in [mirror.dest.id for mirror in self.mirrors[dest.id]]:
            raise commands.BadArgument('This would create a circular mirror.')

        mirror = ChannelMirror(origin, dest, None, True)

        if mirror in flatten(self.mirrors.values()):
            raise commands.BadArgument('This mirror already exists.')

        dest_webhook = await dest.create_webhook(name=f'Mirror from {origin}@{origin.guild}')
        mirror.webhook = dest_webhook

        query = 'INSERT INTO mirrors (origin, destination, webhook, enabled) VALUES ($1, $2, $3, $4);'
        await self.bot.db.pool.execute(query, *await mirror.to_tuple())

        self.append_mirror(mirror)
        await ctx.send(f'Added {mirror}')

    @mirror.command(aliases=['delete'])
    @ack
    async def remove(self, ctx, origin: GlobalTextChannelConverter, dest: GlobalTextChannelConverter):
        try:
            mirrors = self.mirrors[origin.id]
            mirror = [m for m in mirrors if m.dest == dest].pop()
        except IndexError:
            raise commands.BadArgument('This mirror does not exist.')
        except KeyError:
            raise commands.BadArgument(f'Channel {origin.mention} has no mirrors.')

        if mirror.webhook:
            await mirror.webhook.delete()

        mirrors.remove(mirror)

        query = 'DELETE FROM mirrors WHERE origin = $1 and destination = $2;'
        await self.bot.db.pool.execute(query, origin.id, dest.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)

        if ctx.valid or message.author == self.bot.user or message.channel.id not in self.mirrors:
            return

        mirrors = self.mirrors[message.channel.id]
        for mirror in mirrors:
            if not mirror.enabled:
                continue

            author = message.author
            files = [await attachment.to_file() for attachment in message.attachments]
            await mirror.webhook.send(message.clean_content, username=author.name, avatar_url=author.avatar_url,
                                      files=files)
