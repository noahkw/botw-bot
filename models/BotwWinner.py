from models.Idol import Idol


class BotwWinner:
    def __init__(self, member, idol, timestamp):
        self.member = member
        self.idol = idol
        self.timestamp = timestamp

    def __eq__(self, other):
        if not isinstance(other, BotwWinner):
            return NotImplemented
        return self.member == other.member and self.idol == other.idol and self.timestamp == other.timestamp

    def to_dict(self):
        return {
            'member': self.member.id,
            'idol': self.idol.to_dict(),
            'timestamp': self.timestamp
        }

    @staticmethod
    def from_dict(source, bot):
        return BotwWinner(bot.get_user(source['member']),
                          Idol.from_dict(source['idol']), source['timestamp'])