from discord import Embed, User


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
    def add_to_embed(self, embed):
        if not self.hidden:
            embed.set_image(url=self.value)


class Profile:
    __slots__ = (
        "_bot",
        "_user",
        "_items",
    )
    ITEMS_DB = ("location",)

    def __init__(self, bot, user: User, location):
        self._user = user
        self._bot = bot

        self._items = {
            "location": ProfileItem("Location", location, hidden=True),
            "avatar": AvatarItem(None, user.avatar_url, hidden=False),
            "created_at": ProfileItem("Joined Discord", user.created_at, hidden=False),
        }

    def __getattr__(self, item):
        return self._items[item].value

    @staticmethod
    def from_record(source, bot):
        user = bot.get_user(source["user"])

        return Profile(bot, user, *[source[key] for key in Profile.ITEMS_DB])

    def to_tuple(self):
        return tuple(
            [self._user.id] + [self._items[item].value for item in self.ITEMS_DB]
        )

    def to_embed(self):
        embed = Embed(title=f"Profile of {self._user}")

        for item in self._items.values():
            item.add_to_embed(embed)
        return embed
