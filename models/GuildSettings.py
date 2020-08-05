from enum import Enum

from discord import Embed


class BotwState(Enum):
    DEFAULT = 'DEFAULT'
    WINNER_CHOSEN = 'WINNER_CHOSEN'
    SKIP = 'SKIP'


class SettingsItem:
    def __init__(self, name, value):
        self.name = name
        self._value = value

    def add_to_embed(self, embed):
        embed.add_field(name=self.name, value=self.value if self.value else 'not set')

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def db_value(self):
        return self.value

    def update(self, value):
        self.value = value


class DiscordModelItem(SettingsItem):
    def __init__(self, name, value, get_function):
        super().__init__(name, get_function(value))

    def add_to_embed(self, embed):
        embed.add_field(name=self.name, value=self.value.mention if self.value else 'not set')

    def db_value(self):
        return self.value.id if self.value else None


class BotwStateItem(SettingsItem):
    def __init__(self, name, value):
        super().__init__(name, BotwState(value))

    def add_to_embed(self, embed):
        if self.value:
            embed.add_field(name=self.name, value=self.value.name)

    def db_value(self):
        return self.value.name if self.value else None


class GreeterItem(SettingsItem):
    def __init__(self, name, get_function, kwargs):
        self.channel = get_function(kwargs.pop('channel', None))
        self.template = kwargs.pop('template', None)
        super().__init__(name, (self.channel, self.template))

    def add_to_embed(self, embed):
        pass

    def update(self, *values):
        channel, template = values
        self.value = (channel, template)
        self.channel = channel
        self.template = template

    def db_value(self):
        return {
            'channel': self.channel.id if self.channel else None,
            'template': self.template if self.template else None
        }


class GuildSettings:
    __slots__ = (
        'guild', 'botw_enabled', 'botw_state', 'emoji_channel', 'prefix', 'join_greeter', 'leave_greeter',
        'botw_channel', 'botw_nominations_channel')
    __items = __slots__[1:]

    def __init__(self, guild, botw_enabled=False, botw_state=BotwState.DEFAULT, botw_channel=None,
                 botw_nominations_channel=None, emoji_channel=None, prefix=None, join_greeter=None, leave_greeter=None):
        self.guild = guild

        self.botw_enabled = SettingsItem('BotW enabled', botw_enabled)
        self.botw_state = BotwStateItem('BotW state', botw_state)
        self.botw_channel = DiscordModelItem('BotW channel', botw_channel, guild.get_channel)
        self.botw_nominations_channel = DiscordModelItem('BotW nominations channel', botw_nominations_channel,
                                                         guild.get_channel)

        self.emoji_channel = DiscordModelItem('Emoji channel', emoji_channel, guild.get_channel)
        self.prefix = SettingsItem('Prefix', prefix)
        self.join_greeter = GreeterItem('Join greeter', guild.get_channel, join_greeter if join_greeter else {})
        self.leave_greeter = GreeterItem('Leave greeter', guild.get_channel, leave_greeter if leave_greeter else {})

    def to_dict(self):
        return {
            settings_item: getattr(self, settings_item).db_value() for settings_item in GuildSettings.__items
        }

    def update(self, attr, *values):
        item = getattr(self, attr)
        item.update(*values)
        return item.db_value()

    @staticmethod
    def from_dict(guild, source):
        kwargs = {}
        for item in GuildSettings.__items:
            kwargs[item] = source.pop(item, None)
        return GuildSettings(guild, **kwargs)

    def to_embed(self):
        embed = Embed(title=f'Settings of {self.guild}')

        for item in self.__items:
            getattr(self, item).add_to_embed(embed)
        return embed
