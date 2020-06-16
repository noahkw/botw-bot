from discord import Embed


class Profile:
    def __init__(self, location=None):
        self.location = location

    def to_dict(self):
        return {
            'location': self.location
        }

    @staticmethod
    def from_dict(source):
        return Profile(location=source['location'])

    def to_embed(self, member):
        embed = Embed(title=f'Profile of {member}')
        embed.add_field(name='Location', value=self.location)

        return embed
