import logging

from discord.ext import commands

from cogs import CustomCog, AinitMixin
from models import ChannelMirror
from util import flatten, ack, auto_help

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Mirroring(bot))


class TextChannelConverter(commands.Converter):
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
        self.mirrors_collection = self.bot.config['mirroring']['mirrors_collection']

        super(AinitMixin).__init__()

    async def _ainit(self):
        _mirrors = await self.bot.db.get(self.mirrors_collection)

        for _mirror in _mirrors:
            mirror = await ChannelMirror.from_dict(_mirror.to_dict(), self.bot, _mirror.id)
            self.append_mirror(mirror)

        logger.info(f'# Initial mirrors from db: {len(self.mirrors)}')

    @auto_help
    @commands.group(brief='Create channel mirrors between servers')
    @commands.is_owner()
    async def mirror(self, ctx):
        pass

    def append_mirror(self, mirror):
        if mirror.origin in self.mirrors:
            self.mirrors[mirror.origin].append(mirror)
        else:
            self.mirrors[mirror.origin] = [mirror]

    @mirror.command()
    async def add(self, ctx, origin: TextChannelConverter, dest: TextChannelConverter):
        if origin == dest:
            raise commands.BadArgument('Cannot mirror a channel to itself.')

        mirror = ChannelMirror(None, origin, dest, None, True)
        if mirror in flatten(self.mirrors.values()):
            raise commands.BadArgument('This mirror already exists.')

        dest_webhook = await dest.create_webhook(name=f'Mirror from {origin}@{origin.guild}')
        mirror.webhook = dest_webhook

        id_ = await self.bot.db.set_get_id(self.mirrors_collection, mirror.to_dict())
        mirror.id = id_

        self.append_mirror(mirror)
        await ctx.send(f'Added channel mirror from {origin.mention}@`{origin.guild}` to {dest.mention}@`{dest.guild}`')

    @mirror.command(aliases=['delete'])
    @ack
    async def remove(self, ctx, origin: TextChannelConverter, dest: TextChannelConverter):
        mirrors = self.mirrors[origin]
        try:
            mirror = [m for m in mirrors if m.dest == dest].pop()
        except IndexError:
            raise commands.BadArgument('This mirror does not exist.')

        mirrors.remove(mirror)
        await mirror.webhook.delete()
        await self.bot.db.delete(self.mirrors_collection, mirror.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)

        if ctx.valid or message.author == self.bot.user or message.channel not in self.mirrors:
            return

        mirrors = self.mirrors[message.channel]
        for mirror in mirrors:
            if not mirror.enabled:
                continue

            author = message.author
            files = [await attachment.to_file() for attachment in message.attachments]
            await mirror.webhook.send(message.clean_content, username=author.name, avatar_url=author.avatar_url,
                                      files=files)
