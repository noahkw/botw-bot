from enum import Enum

from discord import Embed


class BotwState(Enum):
    DEFAULT = 'DEFAULT'
    WINNER_CHOSEN = 'WINNER_CHOSEN'
    SKIP = 'SKIP'


class GuildSettings:
    def __init__(self, botw_state=BotwState.DEFAULT):
        self.botw_state = botw_state

    def to_dict(self):
        return {
            'botw_state': self.botw_state.name,
        }

    @staticmethod
    def from_dict(source):
        return GuildSettings(botw_state=BotwState(source['botw_state']))

    def to_embed(self, guild):
        embed = Embed(title=f'Settings of {guild}')
        embed.add_field(name='botw_sate', value=str(self.botw_state))

        return embed
