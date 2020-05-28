class Reminder:
    def __init__(self, id_, user, time, content, done=False):
        self.id = id_
        self.user = user
        self.time = time
        self.content = content
        self.done = done

    def __eq__(self, other):
        if not isinstance(other, Reminder):
            return NotImplemented
        return self.id == other.id

    def to_dict(self):
        return {
            'id': self.id,
            'user': self.user,
            'time': self.time,
            'content': self.content,
            'done': self.done
        }

    @staticmethod
    def from_dict(source, bot, id_=None):
        return Reminder(id_, bot.get_user(source['user']), source['time'], source['content'], source['done'])

    def __str__(self):
        return f"Reminder {self.id}: {self.user} at {self.time} to {self.content} ({'not ' if not self.done else ''}done)"
