import asyncio
import logging
import random
from typing import List

import discord
import pendulum
from dateparser import parse
from discord.ext import commands, tasks
from discord.ext.menus import MenuPages

import db
from const import CROSS_EMOJI
from menu import Confirm, BotwWinnerListSource
from models import BotwWinner, BotwState, Idol, Nomination
from models.botw import BotwSettings
from util import ack, auto_help, BoolConverter

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(BiasOfTheWeek(bot))


def has_winner_role():
    async def predicate(ctx):
        async with ctx.bot.Session() as session:
            botw_settings = await db.get_botw_settings(session, ctx.guild.id)
            return (
                botw_settings
                and botw_settings.winner_changes
                and ctx.bot.config["cogs"]["biasoftheweek"]["winner_role_name"]
                in [role.name for role in ctx.message.author.roles]
            )

    return commands.check(predicate)


def botw_enabled():
    async def predicate(ctx):
        async with ctx.bot.Session() as session:
            botw_settings = await db.get_botw_settings(session, ctx.guild.id)
            return botw_settings and botw_settings.enabled

    return commands.check(predicate)


class NoWinnerException(Exception):
    pass


class BiasOfTheWeek(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.past_winners_time = self.bot.config["cogs"]["biasoftheweek"][
            "past_winners_time"
        ]
        self.winner_day = self.bot.config["cogs"]["biasoftheweek"]["winner_day"]
        self.winner_role_name = self.bot.config["cogs"]["biasoftheweek"][
            "winner_role_name"
        ]
        self.announcement_day = divmod((self.winner_day - 3), 7)[1]
        self._loop.start()

        Nomination.inject_bot(bot)
        BotwWinner.inject_bot(bot)
        BotwSettings.inject_bot(bot)

    def cog_unload(self):
        self._loop.stop()

    async def _add_winner(
        self, session, guild: discord.Guild, date, idol: Idol, member: discord.Member
    ):
        botw_winner = BotwWinner(
            _guild=guild.id,
            _member=member.id,
            idol_group=idol.group,
            idol_name=idol.name,
            date=date,
        )
        session.add(botw_winner)

    async def _set_state(self, session, guild: discord.Guild, state: BotwState):
        botw_settings = BotwSettings(_guild=guild.id, state=state)
        await session.merge(botw_settings)
        await session.flush()

    async def _pick_winner(
        self, session, guild: discord.Guild, nominations: List[Nomination], silent=False
    ):
        nomination = random.choice(nominations)
        pick = nomination.idol
        member = nomination.member

        nominations.remove(nomination)
        await db.delete_nominations(session, guild.id, nomination._member)

        while not nomination.member and len(nominations) > 0:
            # member is not in cache, try to pick another winner
            nomination = random.choice(nominations)
            pick = nomination.idol
            member = nomination.member

            nominations.remove(nomination)
            await db.delete_nominations(session, guild.id, nomination._member)

        botw_settings = await db.get_botw_settings(session, guild.id)

        # could not pick a winner, notify
        if not nomination.member:
            await botw_settings.nominations_channel.send(
                "Could not pick a winner for this week's BotW."
            )
            raise NoWinnerException

        # Assign BotW winner role on next wednesday at 00:00 UTC
        now = pendulum.now("UTC")
        assign_date = now.next(self.winner_day)

        await botw_settings.nominations_channel.send(
            f"Bias of the Week ({now.week_of_year}-{now.year}): "
            f"{member if silent else member.mention}'s pick **{pick}**. "
            f"You will be assigned the role "
            f"*{self.winner_role_name}* on "
            f"{assign_date.to_cookie_string()}."
        )

        await self._add_winner(session, guild, now, pick, member)

    async def _assign_winner_role(
        self,
        guild: discord.Guild,
        winner: BotwWinner,
        botw_channel: discord.TextChannel,
        nominations_channel: discord.TextChannel,
        winner_changes: bool,
    ):
        member = winner.member
        logger.info(f"Assigning winner role to {member} in {guild}")
        member = guild.get_member(member.id)
        botw_winner_role = discord.utils.get(guild.roles, name=self.winner_role_name)
        await member.add_roles(botw_winner_role)
        await member.send(
            f"Hi, your pick **{winner.idol}** won this week's BotW. Congratulations!\n"
            f"You may now post your pics and gfys in {botw_channel.mention}."
        )

        if winner_changes:
            await member.send(
                f"Don't forget to change the server name/icon using `.botw [name|icon]` "
                f"in {nominations_channel.mention}."
            )

    async def _remove_winner_role(self, guild: discord.Guild, winner: BotwWinner):
        member = winner.member
        logger.info(f"Removing winner role from {member} in {guild}")
        member = guild.get_member(member.id)
        botw_winner_role = discord.utils.get(guild.roles, name=self.winner_role_name)
        await member.remove_roles(botw_winner_role)

    async def _set_nomination(self, ctx, session, idol: Idol, old_idol: Idol = None):
        guild = ctx.guild
        member = ctx.author

        botw_nomination = Nomination(
            _guild=guild.id,
            _member=member.id,
            idol_group=idol.group,
            idol_name=idol.name,
        )

        await session.merge(botw_nomination)

        await ctx.send(
            f"{ctx.author} nominates **{idol}** instead of **{old_idol}**."
            if old_idol
            else f"{ctx.author} nominates **{idol}**."
        )

    async def _disable(self, session, guild: int):
        logger.info("Disabling botw in guild %d", guild)
        botw_settings = BotwSettings(_guild=guild, enabled=False)
        await session.merge(botw_settings)

    async def _set_channel_name(self, channel: discord.TextChannel, winner: BotwWinner):
        try:
            # try to edit the channel name, pass if we're not allowed to
            channel_name = f"botw-{winner.idol}-{winner.member.name}"
            await channel.edit(name=channel_name)
        except discord.Forbidden:
            pass

    async def cog_command_error(self, ctx, error):
        if hasattr(ctx.command, "on_error"):
            return

        if isinstance(error, commands.CheckFailure):
            await ctx.send("BotW has not been enabled in this server.")
        else:
            logger.exception(error)

    @auto_help
    @commands.group(
        name="biasoftheweek",
        aliases=["botw"],
        brief="Organize Bias of the Week events",
        invoke_without_command=True,
    )
    @botw_enabled()
    async def biasoftheweek(self, ctx):
        await ctx.send_help(self.biasoftheweek)

    @biasoftheweek.command(brief="Sets up BotW in the server")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx):
        def check(m):
            return m.channel == ctx.channel and m.author == ctx.author

        channel_converter = commands.TextChannelConverter()

        await ctx.send(
            "Okay, let's set up Bias of the Week in this server. "
            "Which channel do you want winners to post in? (Reply with a mention or an ID)"
        )

        try:
            botw_channel = await self.bot.wait_for("message", check=check, timeout=60.0)
            botw_channel = await channel_converter.convert(ctx, botw_channel.content)

            await ctx.send(
                "What channel should I send the winner announcement to? (Reply with a mention or an ID)"
            )
            nominations_channel = await self.bot.wait_for(
                "message", check=check, timeout=60.0
            )
            nominations_channel = await channel_converter.convert(
                ctx, nominations_channel.content
            )

            await ctx.send(
                "Should winners be able to change the server icon and name? (yes/no)"
            )
            botw_winner_changes = await self.bot.wait_for(
                "message", check=check, timeout=60.0
            )
            botw_winner_changes = await BoolConverter().convert(
                ctx, botw_winner_changes.content
            )
        except asyncio.TimeoutError:
            await ctx.send(
                f"Timed out.\nPlease restart the setup using `{ctx.prefix}botw setup`."
            )
        except commands.CommandError as e:
            await ctx.send(
                f"{e}\nPlease restart the setup using `{ctx.prefix}botw setup`."
            )
        else:
            async with self.bot.Session() as session:
                botw_settings = BotwSettings(
                    _guild=ctx.guild.id,
                    _botw_channel=botw_channel.id,
                    _nominations_channel=nominations_channel.id,
                    winner_changes=botw_winner_changes,
                )

                await session.merge(botw_settings)
                await session.commit()

            # create role
            if role := discord.utils.get(ctx.guild.roles, name=self.winner_role_name):
                # botw role exists
                pass
            else:  # need to create botw role
                try:
                    role = await ctx.guild.create_role(
                        name=self.winner_role_name, reason="BotW setup"
                    )
                except discord.Forbidden:
                    await ctx.send(
                        f"Could not create role `{self.winner_role_name}`. Please create it yourself and"
                        f" make sure it has send message permissions in {botw_channel.mention}."
                    )

            if role:
                try:
                    overwrites = botw_channel.overwrites
                    overwrites[role] = discord.PermissionOverwrite(send_messages=True)
                    await botw_channel.edit(overwrites=overwrites, reason="BotW setup")
                except discord.Forbidden:
                    pass

            await ctx.send(
                f"Bias of the Week is now enabled in this server! `{ctx.prefix}botw disable` to disable."
            )
            logger.info(
                f"BotW was set up in {ctx.guild}: %s, %s, %s",
                botw_channel,
                nominations_channel,
                botw_winner_changes,
            )

    @biasoftheweek.command(brief="Disable BotW in the server")
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx):
        async with self.bot.Session() as session:
            await self._disable(session, ctx.guild.id)
            await session.commit()

        await ctx.send(
            f"Bias of the Week is now disabled in this server! `{ctx.prefix}botw setup` to re-enable it."
        )

    @biasoftheweek.command(brief="Nominates an idol")
    @botw_enabled()
    async def nominate(
        self, ctx, group: commands.clean_content, *, name: commands.clean_content
    ):
        """
        Nominates an idol for next week's Bias of the Week.

        Example usage:
        `{prefix}botw nominate "Red Velvet" "Irene"`
        """
        async with self.bot.Session() as session:
            idol = Idol(group=group, name=name)

            best_match = await db.get_similar_idol(session, idol)

            if best_match:
                if not best_match == idol:
                    confirm_match = await Confirm(
                        f"**@{ctx.author}**, did you mean **{best_match}**?"
                    ).prompt(ctx)
                    if confirm_match:
                        idol = best_match

            if await db.get_nomination_dupe(session, ctx.guild.id, idol):
                raise commands.BadArgument(
                    f"**{idol}** has already been nominated. Please nominate someone else."
                )
            elif await db.get_past_win(
                session,
                ctx.guild.id,
                idol,
                pendulum.now("UTC").subtract(days=self.past_winners_time),
            ):
                # check whether idol has won in the past
                raise commands.BadArgument(
                    f"**{idol}** has already won in the past `{self.past_winners_time}` days. "
                    f"Please nominate someone else."
                )
            elif nomination := await db.get_botw_nomination(
                session, ctx.guild.id, ctx.author.id
            ):
                old_idol = nomination.idol

                confirm_override = await Confirm(
                    f"Your current nomination is **{old_idol}**. "
                    f"Do you want to override it?"
                ).prompt(ctx)

                if confirm_override:
                    await self._set_nomination(ctx, session, idol, old_idol)
            else:
                await self._set_nomination(ctx, session, idol)

            await session.commit()

    @biasoftheweek.command(brief="Clears your nomination")
    @botw_enabled()
    @ack
    async def clear(self, ctx):
        """
        Clears your nomination.
        """
        async with self.bot.Session() as session:
            await db.delete_nominations(session, ctx.guild.id, ctx.author.id)
            await session.commit()

    @biasoftheweek.command(aliases=["clearall"], brief="Clears a member's nomination")
    @botw_enabled()
    @commands.has_permissions(administrator=True)
    @ack
    async def clearother(self, ctx, member: discord.Member = None):
        """
        Clears a member's nomination.
        Clears all of the guild's nominations if no member was specified.
        """
        async with self.bot.Session() as session:
            if not member:
                confirm = await Confirm(
                    f"**{ctx.author}**, do you really want to clear "
                    f"this guild's nominations?"
                ).prompt(ctx)
                if confirm:
                    await db.delete_nominations(session, ctx.guild.id)
            else:
                await db.delete_nominations(session, ctx.guild.id, member.id)

            await session.commit()

    @biasoftheweek.command(brief="Displays the current nominations")
    @botw_enabled()
    async def nominations(self, ctx):
        async with self.bot.Session() as session:
            nominations = await db.get_botw_nominations(session, ctx.guild.id)

            if nominations:
                embed = discord.Embed(title="Bias of the Week nominations")
                for nomination in nominations:
                    embed.add_field(**nomination.to_field())

                await ctx.send(embed=embed)
            else:
                await ctx.send("So far, no idols have been nominated.")

    @biasoftheweek.command(brief="Manually picks a winner")
    @botw_enabled()
    @commands.has_permissions(administrator=True)
    async def winner(self, ctx, silent: bool = False):
        """
        Manually picks a winner.

        Do not use unless you know what you are doing! It will probably result in the picked winner getting skipped!
        """
        async with self.bot.Session() as session:
            await self._pick_winner(
                session,
                ctx.guild,
                await db.get_botw_nominations(session, ctx.guild.id),
                silent=silent,
            )
            await session.commit()

    @biasoftheweek.command(brief="Skips next week's BotW draw")
    @botw_enabled()
    @commands.has_permissions(administrator=True)
    async def skip(self, ctx):
        async with self.bot.Session() as session:
            botw_settings = await db.get_botw_settings(session, ctx.guild.id)

            if botw_settings.state == BotwState.WINNER_CHOSEN:
                raise commands.BadArgument(
                    "Can't skip because the current winner has not been notified yet."
                )

            await self._set_state(
                session,
                ctx.guild,
                BotwState.DEFAULT
                if botw_settings.state == BotwState.SKIP
                else BotwState.SKIP,
            )

            next_announcement = pendulum.now("UTC").next(self.announcement_day)
            await ctx.send(
                f"BotW Winner selection on `{next_announcement.to_cookie_string()}` is "
                f'now {"" if botw_settings.state == BotwState.SKIP else "**not** "}being skipped.'
            )

            await session.commit()

    @biasoftheweek.command(brief="Displays past BotW winners")
    @botw_enabled()
    async def history(self, ctx):
        async with self.bot.Session() as session:
            if (
                len(past_winners := await db.get_botw_winners(session, ctx.guild.id))
                > 0
            ):
                past_winners = sorted(past_winners, key=lambda w: w.date, reverse=True)
                pages = MenuPages(
                    source=BotwWinnerListSource(past_winners, self.winner_day),
                    clear_reactions_after=True,
                )
                await pages.start(ctx)
            else:
                await ctx.send("So far there have been no winners.")

    @biasoftheweek.command(
        name="servername", aliases=["name"], brief="Changes the server name"
    )
    @botw_enabled()
    @has_winner_role()
    @ack
    async def server_name(self, ctx, *, name):
        await ctx.guild.edit(name=name)

    @server_name.error
    async def server_name_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("Only the current BotW winner may change the server name.")

    @biasoftheweek.command(brief="Changes the server icon")
    @botw_enabled()
    @has_winner_role()
    @ack
    async def icon(self, ctx):
        try:
            file = await ctx.message.attachments[0].read()
            await ctx.guild.edit(icon=file)
        except IndexError:
            raise commands.BadArgument("Icon missing.")

    @icon.error
    async def icon_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("Only the current BotW winner may change the server icon.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Attach the icon to your message.")
        else:
            await ctx.message.add_reaction(CROSS_EMOJI)
            logger.error(error)

    @biasoftheweek.command(brief="Manually adds a past BotW winner")
    @botw_enabled()
    @commands.has_permissions(administrator=True)
    @ack
    async def addwinner(self, ctx, member: discord.Member, starting_day, group, name):
        """
        Manually adds a past BotW winner.

        Example usage:
        `{prefix}botw addwinner @MemberX 2020-08-05 "Red Velvet" "Irene"`
        """
        day = parse(starting_day)
        day = pendulum.instance(day)

        prev_announcement_day = day.previous(self.announcement_day + 1)

        async with self.bot.Session() as session:
            await self._add_winner(
                session, ctx.guild, prev_announcement_day, Idol(group, name), member
            )
            await session.commit()

    @biasoftheweek.command(name="load", brief="Parses a file containing idol names")
    @commands.is_owner()
    async def load_idols(self, ctx):
        try:
            idols_attachment = ctx.message.attachments[0]
        except IndexError:
            raise commands.BadArgument("Attach a file.")

        text = (await idols_attachment.read()).decode("UTF-8")
        lines = text.splitlines()
        lines_tokenized = [line.split("\t") for line in lines]

        async with self.bot.Session() as session:
            with ctx.typing():
                await db.delete_idols(session)

                idols = [
                    Idol(group=group, name=name) for group, name in lines_tokenized
                ]
                session.add_all(idols)

                await session.commit()

        await ctx.send(f"Successfully loaded `{len(lines)}` idols.")

    @biasoftheweek.command(brief="Displays the guild's BotW settings")
    @botw_enabled()
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        async with self.bot.Session() as session:
            botw_settings = await db.get_botw_settings(session, ctx.guild.id)

            embed = (
                discord.Embed(
                    title=f"BotW settings of {ctx.guild}",
                    description=f"Use `{ctx.prefix}botw setup` to change these.",
                )
                .set_thumbnail(url=ctx.guild.icon_url)
                .add_field(name="Enabled", value=botw_settings.enabled)
                .add_field(
                    name="BotW channel",
                    value=botw_settings.botw_channel.mention,
                )
                .add_field(
                    name="Winner announcement channel",
                    value=botw_settings.nominations_channel.mention,
                )
                .add_field(name="State", value=botw_settings.state.value)
            )

            await ctx.send(embed=embed)

    @biasoftheweek.command(brief="Sets the BotW state in the server")
    @commands.is_owner()
    async def state(self, ctx, state):
        async with self.bot.Session() as session:
            state = BotwState(state)
            await self._set_state(session, ctx.guild, state)
            await session.commit()

    @tasks.loop(hours=1.0)
    async def _loop(self):
        # pendulum.set_test_now(pendulum.now("UTC").next(self.winner_day))
        logger.info("Hourly loop running")
        now = pendulum.now("UTC")

        async with self.bot.Session() as session:
            # pick winner on announcement day
            if now.day_of_week == self.announcement_day and now.hour == 0:
                settings_enabled = await db.get_botw_settings(session)
                for guild_settings in settings_enabled:
                    if (
                        not guild_settings.guild
                    ):  # we're not in the guild anymore, disable botw
                        await self._disable(session, guild_settings._guild)
                        continue

                    nominations = await db.get_botw_nominations(
                        session, guild_settings._guild
                    )

                    if (
                        guild_settings.state
                        not in (BotwState.SKIP, BotwState.WINNER_CHOSEN)
                        and len(nominations) > 0
                    ):
                        try:
                            await self._pick_winner(
                                session, guild_settings.guild, nominations
                            )
                            await self._set_state(
                                session, guild_settings.guild, BotwState.WINNER_CHOSEN
                            )
                        except NoWinnerException:
                            logger.info(
                                f"Could not pick a valid winner in {guild_settings.guild}"
                            )
                    else:
                        logger.info(
                            f"Skipping BotW winner selection in {guild_settings.guild}"
                        )

            # assign role on winner day
            elif now.day_of_week == self.winner_day and now.hour == 0:
                settings_enabled = await db.get_botw_settings(session)
                for guild_settings in settings_enabled:
                    if (
                        not guild_settings.guild
                    ):  # we're not in the guild anymore, disable botw
                        await self._disable(session, guild_settings._guild)
                        continue

                    if guild_settings.state not in (BotwState.SKIP, BotwState.DEFAULT):
                        past_winners = await db.get_botw_winners(
                            session, guild_settings._guild
                        )

                        if len(past_winners) >= 2:
                            winner, previous_winner = sorted(
                                past_winners, key=lambda w: w.date, reverse=True
                            )[0:2]
                            try:  # remove previous winner's role if possible
                                await self._remove_winner_role(
                                    guild_settings.guild, previous_winner
                                )
                            except (discord.Forbidden, discord.HTTPException):
                                pass
                        else:
                            winner = past_winners[0]

                        await self._set_channel_name(
                            guild_settings.botw_channel, winner
                        )

                        try:  # assign winner role if possible
                            await self._assign_winner_role(
                                guild_settings.guild,
                                winner,
                                guild_settings.botw_channel,
                                guild_settings.nominations_channel,
                                guild_settings.winner_changes,
                            )
                        except (discord.Forbidden, AttributeError):
                            await guild_settings.nominations_channel.send(
                                f"Couldn't assign the winner role to {winner.member}. "
                                f"They either left or I am not allowed to assign roles."
                            )
                    else:
                        logger.info(
                            f"Skipping BotW winner role assignment in {guild_settings.guild}"
                        )

                    await self._set_state(
                        session, guild_settings.guild, BotwState.DEFAULT
                    )

            await session.commit()

    @_loop.before_loop
    async def loop_before(self):
        await self.bot.wait_until_ready()
