from sqlalchemy import select

from models.guild_settings import GuildSettings
from models.tag import Tag
from models.reminder import Reminder
from models.channel_mirror import ChannelMirror


async def get_guild_settings(session):
    statement = select(GuildSettings)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_tags(session):
    statement = select(Tag)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_reminders(session, user_id=None):
    if user_id:
        statement = select(Reminder).where(
            (Reminder._user == user_id) & (Reminder.done == False)  # noqa
        )
    else:
        statement = select(Reminder).where(Reminder.done == False)  # noqa

    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_reminder(session, reminder_id):
    statement = select(Reminder).where(Reminder.reminder_id == reminder_id)
    result = (await session.execute(statement)).one()

    return result[0] if result else None


async def get_mirrors(session):
    statement = select(ChannelMirror)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]
