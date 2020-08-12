from models.Idol import Idol


class Nomination:
    def __init__(self, member, guild, idol):
        self.member = member
        self.guild = guild
        self.idol = idol

    def __eq__(self, other):
        if not isinstance(other, Nomination):
            return NotImplemented
        return (self.member == other.member and
                self.guild == other.guild and
                self.idol == other.idol)

    @staticmethod
    def from_record(source, bot):
        guild = bot.get_guild(source['guild'])
        member = bot.get_user(source['member'])
        return Nomination(member, guild, Idol(source['idol_group'], source['idol_name']))

    def to_field(self):
        return {
            'name': str(self.member),
            'value': str(self.idol)
        }

    def __str__(self):
        return f'Nomination {self.member}, {self.idol}, in {self.guild}'

    def __repr__(self):
        return f'<{str(self)}>'
