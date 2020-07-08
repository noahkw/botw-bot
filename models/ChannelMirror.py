from discord import utils


class ChannelMirror:
    def __init__(self, id_, origin, dest, webhook, enabled=True):
        self.id = id_
        self.origin = origin
        self.dest = dest
        self.webhook = webhook
        self.enabled = enabled

    def to_dict(self):
        return {
            'origin': self.origin.id,
            'dest': self.dest.id,
            'webhook': self.webhook.id,
            'enabled': self.enabled
        }

    def __eq__(self, other):
        if not isinstance(other, ChannelMirror):
            return NotImplemented
        return self.origin == other.origin and self.dest == other.dest

    @staticmethod
    async def from_dict(source, bot, id_=None):
        dest = bot.get_channel(source['dest'])
        webhook = utils.find(lambda x: x.id == source['webhook'], await dest.webhooks())
        return ChannelMirror(id_, bot.get_channel(source['origin']), dest, webhook, source['enabled'])

    def __repr__(self):
        return f'<ChannelMirror origin={repr(self.origin)} dest={repr(self.dest)} ' \
               f'webhook={repr(self.webhook)} enabled={self.enabled}>'
