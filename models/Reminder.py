class Reminder:
    def __init__(self, id_, user, due, created, content, done=False):
        self.id = id_
        self.user = user
        self.due = due
        self.created = created
        self.content = content
        self.done = done

    def __eq__(self, other):
        if not isinstance(other, Reminder):
            return NotImplemented
        return self.id == other.id

    def to_dict(self):
        return {
            'user': self.user.id,
            'due': self.due.timestamp(),
            'created': self.created.timestamp(),
            'content': self.content,
            'done': self.done
        }

    @staticmethod
    def from_dict(source, bot, id_=None):
        return Reminder(id_, bot.get_user(source['user']), source['due'], source['created'], source['content'],
                        source['done'])

    def __str__(self):
        return f"Reminder {self.id} created {self.created}: {self.user} at {self.due} to {self.content} " \
               f"({'not ' if not self.done else ''}done)"
