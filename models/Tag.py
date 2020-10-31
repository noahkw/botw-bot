import discord
import pendulum
import re

from util import safe_mention

IMAGE_URL_REGEX = r"https?:\/\/.*\.(jpe?g|png|gif)"


class Tag:
    EDITABLE = ["trigger", "reaction", "in_msg"]

    def __init__(
        self, bot, id, date, creator, guild, in_msg, reaction, trigger, use_count
    ):
        self._id = id
        self.trigger = trigger
        self.reaction = reaction
        self.in_msg = in_msg
        self._creator: int = creator
        self._guild: int = guild
        self._use_count = use_count
        self._date = pendulum.instance(date)
        self._bot = bot

    @property
    def id(self):
        return self._id

    @property
    def creator(self):
        return self._bot.get_user(self._creator)

    @property
    def guild(self):
        return self._bot.get_guild(self._guild)

    @property
    def use_count(self):
        return self._use_count

    def increment_use_count(self):
        self._use_count += 1
        return self._use_count

    @property
    def date(self):
        return self._date

    def __str__(self):
        return f"({self.id}) {self.trigger} -> {self.reaction} (creator: {self.creator}, guild: {self.guild})"

    def to_list_element(self, index):
        return f"*{index + 1}*. `{self.id}`: *{self.trigger}* by {self.creator}"

    def __eq__(self, other):
        if not isinstance(other, Tag):
            return NotImplemented
        return (
            str.lower(self.trigger) == str.lower(other.trigger)
            and str.lower(self.reaction) == str.lower(other.reaction)
            and self.guild == other.guild
        )

    def info_embed(self):
        embed = (
            discord.Embed(title=f"Tag `{self.id}`")
            .add_field(name="Trigger", value=self.trigger)
            .add_field(name="Reaction", value=self.reaction)
            .add_field(name="Creator", value=safe_mention(self.creator))
            .add_field(name="Triggers in message", value=str(self.in_msg))
            .add_field(name="Use Count", value=str(self.use_count))
            .set_footer(text=f"Created on {self.date.to_formatted_date_string()}")
        )

        if re.search(IMAGE_URL_REGEX, self.reaction):
            embed.set_image(url=self.reaction)

        return embed

    @staticmethod
    def from_record(source, bot):
        return Tag(bot, *source)
