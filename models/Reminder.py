import pendulum


class Reminder:
    def __init__(self, bot, id, content, created, done, due, user):
        self.id = id
        self._user: int = user
        self.due = pendulum.instance(due)
        self.created = pendulum.instance(created)
        self.content = content
        self.done = done

        self._bot = bot

    @property
    def user(self):
        return self._bot.get_user(self._user)

    def __eq__(self, other):
        if not isinstance(other, Reminder):
            return NotImplemented
        return self.id == other.id

    @staticmethod
    def from_record(source, bot):
        return Reminder(bot, **source)

    def __repr__(self):
        return (
            f"<Reminder id={repr(self.id)} user={self.user} due={repr(self.due)} "
            f"created={repr(self.created)} content={self.content} done={self.done}>"
        )

    def to_field(self):
        return {"name": self.due.to_cookie_string(), "value": self.content}
