import discord
import pendulum
import time


class Tag:
    SPLIT_EMBED_AFTER = 15

    def __init__(self,
                 id_,
                 trigger,
                 reaction,
                 creator,
                 in_msg_trigger=False,
                 use_count=0,
                 creation_date=None):
        self.id = id_
        self.trigger = trigger
        self.reaction = reaction
        self.creator = creator
        self.in_msg_trigger = in_msg_trigger
        self.use_count = use_count
        self.creation_date = time.time(
        ) if creation_date is None else creation_date

    def __str__(self):
        return f'({self.id}) {self.trigger} -> {self.reaction} (creator: {self.creator})'

    def to_list_element(self):
        return f'`{self.id}`: *{self.trigger}* by {self.creator}'

    def __eq__(self, other):
        if not isinstance(other, Tag):
            return NotImplemented
        return str.lower(self.trigger) == str.lower(
            other.trigger) and str.lower(self.reaction) == str.lower(
            other.reaction)

    def to_dict(self):
        return {
            'trigger': self.trigger,
            'reaction': self.reaction,
            'creator': self.creator.id,
            'in_msg_trigger': self.in_msg_trigger,
            'use_count': self.use_count,
            'creation_date': self.creation_date
        }

    def info_embed(self):
        embed = discord.Embed(title=f'Tag `{self.id}`')
        embed.add_field(name='Trigger', value=self.trigger)
        embed.add_field(name='Reaction', value=self.reaction)
        embed.add_field(name='Creator', value=self.creator.mention)
        embed.add_field(name='Triggers in message',
                        value=str(self.in_msg_trigger))
        embed.add_field(name='Use Count', value=str(self.use_count))
        embed.set_footer(
            text=
            f'Created on {pendulum.from_timestamp(self.creation_date).to_formatted_date_string()}'
        )
        return embed

    @staticmethod
    def from_dict(source, bot, id=None):
        return Tag(id,
                   source['trigger'],
                   source['reaction'],
                   bot.get_user(source['creator']),
                   in_msg_trigger=source['in_msg_trigger'],
                   use_count=source['use_count'],
                   creation_date=source['creation_date'])


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


class BotwWinner:
    def __init__(self, member, idol, timestamp):
        self.member = member
        self.idol = idol
        self.timestamp = timestamp

    def __eq__(self, other):
        if not isinstance(other, BotwWinner):
            return NotImplemented
        return self.member == other.member and self.idol == other.idol and self.timestamp == other.timestamp

    def to_dict(self):
        return {
            'member': self.member.id,
            'idol': self.idol.to_dict(),
            'timestamp': self.timestamp
        }

    @staticmethod
    def from_dict(source, bot):
        return BotwWinner(bot.get_user(source['member']),
                          Idol.from_dict(source['idol']), source['timestamp'])


class Job:
    def __init__(self, func, args, exec_time):
        self.func = func
        self.args = args
        self.exec_time = exec_time

    def __eq__(self, other):
        if not isinstance(other, Job):
            return NotImplemented
        return self.func == other.func and self.args == other.args and self.exec_time == other.exec_time

    def to_dict(self):
        return {
            'func': self.func,
            'args': self.args,
            'exec_time': self.exec_time
        }

    @staticmethod
    def from_dict(source):
        return Job(source['func'], source['args'], source['exec_time'])

    def __str__(self):
        return f'Job: {self.func} with arguments {self.args} at {self.exec_time}'
