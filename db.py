import pendulum
from sqlalchemy import select, delete, func, desc

from models import (
    Nomination,
    BotwWinner,
    Idol,
    RoleClear,
    AssignableRole,
    RoleAlias,
    Greeter,
    BotwSettings,
    Profile,
    GuildSettings,
    EmojiSettings,
    Tag,
    Reminder,
    ChannelMirror,
    CommandLog,
    TwtSettings,
    TwtAccounts,
    TwtFilters,
)


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


async def get_profile(session, user_id):
    statement = select(Profile).where(Profile._user == user_id)
    result = (await session.execute(statement)).one()

    return result[0] if result else None


async def get_emoji_settings(session, guild_id):
    statement = select(EmojiSettings).where(EmojiSettings._guild == guild_id)
    result = (await session.execute(statement)).one()

    return result[0] if result else None


async def get_botw_nominations(session, guild_id):
    statement = select(Nomination).where(Nomination._guild == guild_id)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_botw_nomination(session, guild_id, member_id):
    statement = select(Nomination).where(
        (Nomination._guild == guild_id) & (Nomination._member == member_id)
    )
    result = (await session.execute(statement)).first()

    return result[0] if result else None


async def get_twitter_settings(session, guild_id):
    statement = select(TwtSettings).where(TwtSettings._guild == guild_id)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_twitter_accounts(session, account_id=None, _guild=None):
    if _guild and account_id:
        statement = select(TwtAccounts).where(
            (TwtAccounts.account_id == account_id) & (TwtAccounts._guild == _guild)
        )
    elif account_id:
        statement = select(TwtAccounts).where(TwtAccounts.account_id == account_id)
    elif _guild:
        statement = select(TwtAccounts).where(TwtAccounts._guild == _guild)
    else:
        statement = select(TwtAccounts)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_twitter_filters(
    session, hashtag=None, guild_id=None, tag_list=None, guild_list=None
):
    if hashtag and guild_id:
        statement = select(TwtFilters).where(
            (TwtFilters.hashtag == hashtag) & (TwtFilters._guild == guild_id)
        )
    elif guild_id:
        statement = select(TwtFilters).where(TwtFilters._guild == guild_id)
    elif tag_list and guild_list:
        statement = select(TwtFilters).where(
            TwtFilters._guild.in_(guild_list) & TwtFilters.hashtag.in_(tag_list)
        )
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def delete_twitter_filters(session, hashtag, guild_id):
    statement = delete(TwtFilters).where(
        (TwtFilters.hashtag == hashtag) & (TwtFilters._guild == guild_id)
    )

    await session.execute(statement)


async def delete_accounts(session, account_id, guild_id):
    statement = delete(TwtAccounts).where(
        (TwtAccounts.account_id == account_id) & (TwtAccounts._guild == guild_id)
    )

    await session.execute(statement)


async def delete_nominations(session, guild_id, member_id=None):
    if member_id:
        statement = delete(Nomination).where(
            (Nomination._guild == guild_id) & (Nomination._member == member_id)
        )
    else:
        statement = delete(Nomination).where(Nomination._guild == guild_id)

    await session.execute(statement)


async def get_botw_winners(session, guild_id):
    statement = select(BotwWinner).where(BotwWinner._guild == guild_id)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_botw_settings(session, guild_id=None):
    if guild_id:
        statement = select(BotwSettings).where(BotwSettings._guild == guild_id)
        result = (await session.execute(statement)).first()

        return result[0] if result else None
    else:
        statement = select(BotwSettings).where(BotwSettings.enabled == True)  # noqa
        result = (await session.execute(statement)).all()

        return [r for (r,) in result]


async def get_similar_idol(session, idol):
    statement = select(Idol).order_by(
        func.similarity(Idol.group + " " + Idol.name, str(idol)).desc()
    )
    result = (await session.execute(statement)).first()

    return result[0] if result else None


async def get_nomination_dupe(session, guild_id, idol):
    statement = select(Nomination).where(
        (Nomination._guild == guild_id)
        & (Nomination.idol_group == idol.group)
        & (Nomination.idol_name == idol.name)
    )
    result = (await session.execute(statement)).first()

    return result[0] if result else None


async def get_past_win(session, guild_id, idol, date):
    statement = select(BotwWinner).where(
        (BotwWinner._guild == guild_id)
        & (BotwWinner.idol_group == idol.group)
        & (BotwWinner.idol_name == idol.name)
        & (BotwWinner.date > date)
    )
    result = (await session.execute(statement)).first()

    return result[0] if result else None


async def delete_idols(session):
    statement = delete(Idol)
    await session.execute(statement)


async def get_role_clears(session):
    statement = select(RoleClear)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def delete_role_clear(session, member_id, role_id):
    statement = delete(RoleClear).where(
        (RoleClear._member == member_id) & (RoleClear._role == role_id)
    )
    await session.execute(statement)


async def get_role_by_alias(session, guild_id, alias):
    statement = (
        select(AssignableRole)
        .join(RoleAlias)
        .where(
            (AssignableRole._guild == guild_id)
            & (AssignableRole.enabled == True)  # noqa
            & (RoleAlias.alias == alias)
        )
    )
    result = (await session.execute(statement)).first()

    return result[0] if result else None


async def get_roles(session, guild_id):
    statement = select(AssignableRole).where(AssignableRole._guild == guild_id)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_role(session, role_id):
    statement = select(AssignableRole).where(AssignableRole._role == role_id)
    result = (await session.execute(statement)).first()

    return result[0] if result else None


async def delete_role(session, role_id):
    statement = delete(AssignableRole).where((AssignableRole._role == role_id))
    await session.execute(statement)


async def get_greeter(session, guild_id, greeter_type):
    statement = select(Greeter).where(
        (Greeter._guild == guild_id) & (Greeter.type == greeter_type)
    )
    result = (await session.execute(statement)).first()

    return result[0] if result else None


async def delete_greeter(session, guild_id, greeter_type):
    statement = (
        delete(Greeter)
        .where((Greeter._guild == guild_id) & (Greeter.type == greeter_type))
        .returning(Greeter._channel, Greeter.template)
    )
    return (await session.execute(statement)).first()


async def get_command_usage_by(session, by, command_name, weeks):
    by_ = CommandLog._user if by == "user" else CommandLog._guild
    statement = (
        select(by_, CommandLog.command_name, func.count(CommandLog._command_log))
        .where(
            (CommandLog.command_name == command_name)
            & (CommandLog.date >= pendulum.now("UTC").subtract(weeks=weeks))
        )
        .group_by(by_, CommandLog.command_name)
        .order_by(desc(func.count(CommandLog._command_log)))
    )
    result = (await session.execute(statement)).all()

    return result
