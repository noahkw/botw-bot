from models.Idol import Idol


class Nomination:
    def __init__(self, id_, member, guild, idol):
        self.id = id_
        self.member = member
        self.guild = guild
        self.idol = idol

    def __eq__(self, other):
        if not isinstance(other, Nomination):
            return NotImplemented
        return (self.member == other.member and
                self.guild == other.guild and
                self.idol == other.idol)

    def to_dict(self):
        return {
            'member': self.member.id,
            'guild': self.guild.id,
            'idol': self.idol.to_dict()
        }

    @staticmethod
    def from_dict(source, bot, id_=None):
        member = bot.get_user(source.pop('member', None))
        guild = bot.get_guild(source.pop('guild', None))
        idol = Idol.from_dict(source.pop('idol', None))
        return Nomination(id_, member, guild, idol)

    def to_field(self):
        return {
            'name': str(self.member),
            'value': str(self.idol)
        }

    def __str__(self):
        return f'Nomination ({self.id}) {self.member}, {self.idol}, in {self.guild}'

    def __repr__(self):
        return f'<{str(self)}>'
