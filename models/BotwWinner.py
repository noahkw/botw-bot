import pendulum

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
            'timestamp': self.timestamp.timestamp()
        }

    @staticmethod
    def from_dict(source, bot):
        return BotwWinner(bot.get_user(source['member']), Idol.from_dict(source['idol']),
                          pendulum.from_timestamp(source['timestamp']))

    def to_field(self, winner_day):
        week = self.timestamp.week_of_year if self.timestamp.day_of_week < winner_day and \
                                              self.timestamp.day_of_week != 0 else self.timestamp.week_of_year + 1
        year = self.timestamp.year
        return {
            'name': f'{year}-{week}',
            'value': f'{self.idol} by {self.member.mention}'
        }

    def __str__(self):
        return f'BotwWinner {self.member}, {self.idol}, at {self.timestamp})'

    def __repr__(self):
        return str(self)
