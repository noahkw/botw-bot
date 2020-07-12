import time

import discord
import pendulum


class Tag:
    EDITABLE = ['trigger', 'reaction', 'in_msg_trigger']

    def __init__(self, id_, trigger, reaction, creator, guild, in_msg_trigger=False, use_count=0, creation_date=None):
        self.id = id_
        self.trigger = trigger
        self.reaction = reaction
        self.creator = creator
        self.guild = guild
        self.in_msg_trigger = in_msg_trigger
        self.use_count = use_count
        self.creation_date = time.time() if creation_date is None else creation_date

    def __str__(self):
        return f'({self.id}) {self.trigger} -> {self.reaction} (creator: {self.creator}, guild: {self.guild})'

    def to_list_element(self, index):
        return f'*{index + 1}*. `{self.id}`: *{self.trigger}* by {self.creator}'

    def __eq__(self, other):
        if not isinstance(other, Tag):
            return NotImplemented
        return str.lower(self.trigger) == str.lower(other.trigger) and str.lower(self.reaction) == str.lower(
            other.reaction) and self.guild == other.guild

    def to_dict(self):
        return {
            'trigger': self.trigger,
            'reaction': self.reaction,
            'creator': self.creator.id,
            'guild': self.guild.id,
            'in_msg_trigger': self.in_msg_trigger,
            'use_count': self.use_count,
            'creation_date': self.creation_date
        }

    def info_embed(self):
        embed = discord.Embed(title=f'Tag `{self.id}`')
        embed.add_field(name='Trigger', value=self.trigger)
        embed.add_field(name='Reaction', value=self.reaction)
        embed.add_field(name='Creator', value=self.creator.mention)
        embed.add_field(name='Triggers in message', value=str(self.in_msg_trigger))
        embed.add_field(name='Use Count', value=str(self.use_count))
        embed.set_footer(text=f'Created on {pendulum.from_timestamp(self.creation_date).to_formatted_date_string()}')
        return embed

    @staticmethod
    def from_dict(source, bot, id_=None):
        return Tag(id_, source['trigger'], source['reaction'], bot.get_user(source['creator']),
                   bot.get_guild(source['guild']), in_msg_trigger=source['in_msg_trigger'],
                   use_count=source['use_count'], creation_date=source['creation_date'])
