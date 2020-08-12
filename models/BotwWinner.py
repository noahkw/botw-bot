import pendulum

from models.Idol import Idol


class BotwWinner:
    def __init__(self, member, guild, idol, date):
        self.member = member
        self.guild = guild
        self.idol = idol
        self.date = pendulum.instance(date)

    def __eq__(self, other):
        if not isinstance(other, BotwWinner):
            return NotImplemented
        return (self.member == other.member and
                self.guild == other.guild and
                self.idol == other.idol and
                self.date == other.date)

    @staticmethod
    def from_record(source, bot):
        guild = bot.get_user(source['guild'])
        member = bot.get_user(source['member'])
        return BotwWinner(member, guild, Idol(source['idol_group'], source['idol_name']), source['date'])

    def to_field(self, winner_day):
        week = self.date.week_of_year if self.date.day_of_week < winner_day and \
                                         self.date.day_of_week != 0 else self.date.week_of_year + 1
        year = self.date.year
        return {
            'name': f'{year}-{week}',
            'value': f'{self.idol} by {self.member.mention}'
        }

    def __str__(self):
        return f'BotwWinner {self.member}, {self.idol}, at {self.date}, in {self.guild}'

    def __repr__(self):
        return str(self)
