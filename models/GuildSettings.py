from enum import Enum

from discord import Embed


class BotwState(Enum):
    DEFAULT = 'DEFAULT'
    WINNER_CHOSEN = 'WINNER_CHOSEN'
    SKIP = 'SKIP'


class GuildSettings:
    def __init__(self, botw_state=BotwState.DEFAULT, emoji_channel=None):
        self.botw_state = botw_state
        self.emoji_channel = emoji_channel

    def to_dict(self):
        return {
            'botw_state': self.botw_state.name,
            'emoji_channel': self.emoji_channel.id if self.emoji_channel else None
        }

    @staticmethod
    def from_dict(source, bot):
        return GuildSettings(botw_state=BotwState(source['botw_state']),
                             emoji_channel=bot.get_channel(
                                 source['emoji_channel']) if 'emoji_channel' in source else None)

    def to_embed(self, guild):
        embed = Embed(title=f'Settings of {guild}')
        embed.add_field(name='botw_state', value=str(self.botw_state))
        embed.add_field(name='emoji channel', value=self.emoji_channel.mention)

        return embed
