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


class GuildSettings:
    __slots__ = ('guild', 'botw_state', 'emoji_channel', 'prefix',)
    __items__ = __slots__[1:]

    def __init__(self, guild, botw_state=BotwState.DEFAULT, emoji_channel=None, prefix=None):
        self.guild = guild

        self.botw_state = BotwStateItem('BotW state', botw_state)
        self.emoji_channel = DiscordModelItem('Emoji channel', emoji_channel, guild.get_channel)
        self.prefix = SettingsItem('Prefix', prefix)

    def to_dict(self):
        return {
            settings_item: getattr(self, settings_item).db_value() for settings_item in GuildSettings.__items__
        }

    @staticmethod
    def from_dict(guild, source):
        kwargs = {}
        for item in GuildSettings.__items__:
            kwargs[item] = source.pop(item, None)
        return GuildSettings(guild, **kwargs)

    def to_embed(self):
        embed = Embed(title=f'Settings of {self.guild}')

        for item in self.__items__:
            getattr(self, item).add_to_embed(embed)
        return embed
