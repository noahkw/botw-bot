import typing

import pendulum
from sqlalchemy import select, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

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
    TwtSetting,
    TwtAccount,
    TwtSorting,
    TwtFilter,
    RoleSettings,
    GuildCog,
    CustomRole,
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


async def get_twitter_settings(
    session, guild_id=None, guild_list=None, disabled_servers=False
):
    if guild_id:
        statement = select(TwtSetting).where(TwtSetting._guild == guild_id)
        result = (await session.execute(statement)).first()
        return result[0] if result else None
    elif guild_list and disabled_servers:
        statement = select(TwtSetting).where(
            TwtSetting._guild.in_(guild_list) & (not TwtSetting.enabled)
        )
        result = (await session.execute(statement)).all()
        return [r for (r,) in result]
    else:
        raise TypeError("Passed an invalid combination of kwargs")


async def get_twitter_accounts(session, account_id=None, guild_id=None):
    if guild_id and account_id:
        statement = select(TwtAccount).where(
            (TwtAccount.account_id == account_id) & (TwtAccount._guild == guild_id)
        )
    elif account_id:
        statement = select(TwtAccount).where(TwtAccount.account_id == account_id)
    elif guild_id:
        statement = select(TwtAccount).where(TwtAccount._guild == guild_id)
    else:
        statement = select(TwtAccount)

    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_twitter_accounts_distinct(session):
    statement = select(TwtAccount.account_id).distinct()
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_twitter_sorting(
    session, hashtag=None, guild_id=None, tag_list=None, guild_list=None
):
    if hashtag and guild_id:
        statement = select(TwtSorting).where(
            (TwtSorting.hashtag == hashtag) & (TwtSorting._guild == guild_id)
        )
    elif guild_id:
        statement = select(TwtSorting).where(TwtSorting._guild == guild_id)
    elif tag_list and guild_list:
        statement = select(TwtSorting).where(
            TwtSorting._guild.in_(guild_list) & TwtSorting.hashtag.in_(tag_list)
        )
    else:
        raise TypeError("Passed an invalid combination of kwargs")

    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_twitter_filters(
    session, filter_=None, guild_id=None, guild_list=None, word_list=None
):
    if guild_id and filter_:
        statement = select(TwtFilter).where(
            (TwtFilter._filter == filter_) & (TwtFilter._guild == guild_id)
        )
    elif guild_list and word_list:
        statement = select(TwtFilter).where(
            TwtFilter._guild.in_(guild_list) & TwtFilter._filter.in_(word_list)
        )
    elif guild_id:
        statement = select(TwtFilter).where(TwtFilter._guild == guild_id)
    else:
        raise TypeError("Passed an invalid combination of kwargs")

    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def delete_twitter_sorting(session, hashtag, guild_id) -> bool:
    """
    Tries to delete a TwtSorting and returns whether one was actually found and deleted.
    """
    statement = delete(TwtSorting).where(
        (TwtSorting.hashtag == hashtag) & (TwtSorting._guild == guild_id)
    )

    result = await session.execute(statement)
    return result.rowcount > 0


async def delete_accounts(session, account_id, guild_id) -> bool:
    """
    Tries to delete a TwtAccount and returns whether one was actually found and deleted.
    """
    statement = delete(TwtAccount).where(
        (TwtAccount.account_id == account_id) & (TwtAccount._guild == guild_id)
    )

    result = await session.execute(statement)
    return result.rowcount > 0


async def delete_twitter_filters(session, _filter=None, guild_id=None) -> bool:
    """
    Tries to delete a TwtFilter and returns whether one was actually found and deleted.
    """
    if _filter and guild_id:
        statement = delete(TwtFilter).where(
            (TwtFilter._filter == _filter) & (TwtFilter._guild == guild_id)
        )
    else:
        raise TypeError("Passed an invalid combination of kwargs")

    result = await session.execute(statement)
    return result.rowcount > 0


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


async def get_role_clears(session: AsyncSession) -> list[RoleClear]:
    statement = select(RoleClear)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def delete_role_clear(
    session: AsyncSession, member_id: int, role_id: int
) -> None:
    statement = delete(RoleClear).where(
        (RoleClear._member == member_id) & (RoleClear._role == role_id)
    )
    await session.execute(statement)


async def get_role_by_alias(
    session: AsyncSession, guild_id: int, alias: str
) -> typing.Optional[AssignableRole]:
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


async def get_roles(session: AsyncSession, guild_id: int) -> list[AssignableRole]:
    statement = select(AssignableRole).where(AssignableRole._guild == guild_id)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


async def get_role(
    session: AsyncSession, role_id: int
) -> typing.Optional[AssignableRole]:
    statement = select(AssignableRole).where(AssignableRole._role == role_id)
    result = (await session.execute(statement)).first()

    return result[0] if result else None


async def get_role_settings(
    session: AsyncSession, guild_id: int
) -> typing.Optional[RoleSettings]:
    statement = select(RoleSettings).where(RoleSettings._guild == guild_id)
    result = (await session.execute(statement)).first()

    return result[0] if result else None


async def delete_role(session: AsyncSession, role_id: int) -> None:
    statement = delete(AssignableRole).where((AssignableRole._role == role_id))
    await session.execute(statement)


async def delete_custom_role(
    session: AsyncSession, guild_id: int, user_id: int
) -> None:
    statement = delete(CustomRole).where(
        (CustomRole._guild == guild_id) & (CustomRole._user == user_id)
    )
    await session.execute(statement)


async def get_custom_roles(session: AsyncSession) -> list[CustomRole]:
    statement = select(CustomRole)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]


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


async def get_cog_guilds(session, cog_name: str):
    statement = select(GuildCog).where(GuildCog.cog == cog_name)
    result = (await session.execute(statement)).all()

    return [r for (r,) in result]
