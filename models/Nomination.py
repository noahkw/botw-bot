from models.Idol import Idol


class Nomination:
    def __init__(self, bot, member, guild, idol):
        self._member: int = member
        self._guild: int = guild
        self.idol = idol

        self._bot = bot

    @property
    def member(self):
        return self._bot.get_user(self._member)

    @property
    def guild(self):
        return self._bot.get_guild(self._guild)

    def __eq__(self, other):
        if not isinstance(other, Nomination):
            return NotImplemented
        return (
            self._member == other._member
            and self._guild == other._guild
            and self.idol == other.idol
        )

    @staticmethod
    def from_record(source, bot):
        return Nomination(
            bot,
            source["member"],
            source["guild"],
            Idol(source["idol_group"], source["idol_name"]),
        )

    def to_field(self):
        return {"name": str(self.member), "value": str(self.idol)}

    def __str__(self):
        return f"Nomination {self.member}, {self.idol}, in {self.guild}"

    def __repr__(self):
        return f"<{str(self)}>"
