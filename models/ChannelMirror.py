from discord import utils


class ChannelMirror:
    def __init__(self, origin, dest, webhook, enabled=True):
        self.origin = origin
        self.dest = dest
        self.webhook = webhook
        self.enabled = enabled

    def __eq__(self, other):
        if not isinstance(other, ChannelMirror):
            return NotImplemented
        return self.origin == other.origin and self.dest == other.dest

    @staticmethod
    async def from_record(source, bot):
        dest = bot.get_channel(source['destination'])
        webhook = utils.find(lambda x: x.id == source['webhook'], await dest.webhooks())
        mirror = ChannelMirror(bot.get_channel(source['origin']), dest, webhook, source['enabled'])

        if not webhook:  # notify owner that webhook has been deleted; mirror dead
            await bot.get_user(bot.CREATOR_ID).send(f'Mirror\'s webhook has been deleted: {mirror}')

        return mirror

    def __str__(self):
        return f'channel mirror from {self.origin.mention}@`{self.origin.guild}` to ' \
               f'{self.dest.mention}@`{self.dest.guild}`'

    def __repr__(self):
        return f'<ChannelMirror origin={repr(self.origin)} dest={repr(self.dest)} ' \
               f'webhook={repr(self.webhook)} enabled={self.enabled}>'

    async def to_tuple(self):
        return self.origin.id, self.dest.id, self.webhook.id, self.enabled
