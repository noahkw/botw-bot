from discord import Embed


class ProfileItem:
    def __init__(self, name, value, hidden=True):
        self.name = name
        self._value = value
        self.hidden = hidden

    # adds field to given embed (if not hidden)
    def add_to_embed(self, embed):
        if not self.hidden:
            embed.add_field(name=self.name, value=self.value)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value


class AvatarItem(ProfileItem):
    def __init__(self, value, hidden=True):
        super().__init__('Avatar', value, hidden)

    def add_to_embed(self, embed):
        if not self.hidden:
            embed.set_image(url=self.value)


class Profile:
    __slots__ = ('user', 'location', 'avatar', 'created_at', )
    __items__ = __slots__[1:]
    __items_db__ = ('location', )

    def __init__(self, user, location=None):
        self.user = user

        self.location = ProfileItem('Location', location, hidden=True)
        self.avatar = AvatarItem(user.avatar_url, hidden=False)
        self.created_at = ProfileItem('Joined Discord', user.created_at, hidden=False)

    def to_dict(self):
        return {
            'location': self.location.value
        }

    @staticmethod
    def from_dict(user, source):
        kwargs = {}
        for item in Profile.__items_db__:
            kwargs[item] = source.pop(item, None)
        return Profile(user, **kwargs)

    def to_embed(self):
        embed = Embed(title=f'Profile of {self.user}')
        # embed.set_image(url=self.user.avatar_url)

        for item in self.__items__:
            getattr(self, item).add_to_embed(embed)
        return embed
