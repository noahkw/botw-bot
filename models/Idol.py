class Idol:
    def __init__(self, group, name):
        self.group = group
        self.name = name

    def __str__(self):
        return f'{self.group} {self.name}'

    def __eq__(self, other):
        if not isinstance(other, Idol):
            return NotImplemented
        return str.lower(self.group) == str.lower(other.group) and str.lower(
            self.name) == str.lower(other.name)

    def to_dict(self):
        return {'group': self.group, 'name': self.name}

    @staticmethod
    def from_dict(source):
        return Idol(source['group'], source['name'])