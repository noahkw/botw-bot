import asyncio
import typing

import discord
from discord import Interaction, Button, Color, SelectOption, Emoji
from discord.ext import commands
from discord.ui import TextInput, Modal, RoleSelect, Select

import db
from const import COLOR_PICKER_URL, UNICODE_EMOJI
from models import CustomRoleSettings
from util import format_template
from views.base_view import BaseView


class RoleCreatorResult:
    name: str
    color: str
    user_id: int
    emoji: Emoji

    def __init__(self):
        self.name = None
        self.color = None
        self.user_id = None
        self.emoji = None


def role_setup_permission_check(cls):
    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if hasattr(self, "member") and self.member.id != interaction.user.id:
            await interaction.response.send_message(
                "You are not allowed to interact with this message.",
                ephemeral=True,
                delete_after=10.0,
            )
            return False
        elif not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You are not allowed to set up custom roles.",
                ephemeral=True,
                delete_after=10.0,
            )
            return False

        return True

    cls.interaction_check = interaction_check

    return cls


class CallbackView:
    callback: typing.Callable[[typing.Any], typing.Awaitable[typing.Any]]
    result: RoleCreatorResult

    def __init__(self, callback, result):
        super().__init__()
        self.callback = callback
        self.result = result


class RolePicker(RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Choose one role...")

    async def callback(self, interaction: Interaction) -> None:
        role = self.values[0]
        client_member = interaction.guild.get_member(interaction.client.user.id)
        if role.position >= client_member.top_role.position:
            await interaction.response.send_message(
                "Please choose a role the bot can manage, i.e., one that is below its own highest role.",
                ephemeral=True,
                delete_after=120.0,
            )

        await interaction.response.defer()


class EmojiPicker(Select):
    def __init__(self, emojis: tuple[Emoji]):
        options = [
            SelectOption(
                label=emoji.name,
                value=str(emoji.id),
                description="Animated" if emoji.animated else "",
                emoji=emoji,
            )
            for emoji in emojis[:25]
        ]

        super().__init__(
            placeholder="Choose your role's emoji...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()


@role_setup_permission_check
class CustomRoleDisable(BaseView):
    def __init__(self, *args, member: discord.Member):
        super().__init__()
        self.member = member

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.blurple)
    async def confirm(self, interaction: Interaction, button: Button):
        self.stop()

        async with interaction.client.Session() as session:
            role_ids = await db.delete_custom_roles_in_guild(
                session, interaction.guild_id
            )

            async def delete_custom_role(role_id):
                role = interaction.guild.get_role(role_id)

                if role is not None:
                    await role.delete(reason="Disabled custom roles")

            await asyncio.gather(*[delete_custom_role(role_id) for role_id in role_ids])

            await db.delete_custom_role_settings(session, interaction.guild_id)

            await session.commit()
            await interaction.response.send_message(
                f"Deleted `{len(role_ids)}` custom roles and disabled creation.",
            )


class RoleCreatorEmojiPickerView(CallbackView, BaseView):
    def __init__(
        self,
        all_emojis: tuple[Emoji],
        filtered_emojis: tuple[Emoji],
        interaction: Interaction,
        callback,
        result,
    ):
        super().__init__(callback, result)
        self.interaction = interaction
        self.filtered_emojis = filtered_emojis
        self.all_emojis = all_emojis
        self.add_item(EmojiPicker(self.filtered_emojis))

    @staticmethod
    def filter_emoji(emoji, term):
        if term is None:
            return True
        else:
            return emoji.name.lower().startswith(term.lower())

    @discord.ui.button(
        label="Search",
        emoji=UNICODE_EMOJI["INSPECT"],
        style=discord.ButtonStyle.green,
        row=2,
    )
    async def search(self, interaction: Interaction, button: Button):
        modal = RoleCreatorEmojiSearchModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        filtered_emojis = tuple(
            [
                emoji
                for emoji in self.all_emojis
                if RoleCreatorEmojiPickerView.filter_emoji(emoji, modal.result)
            ]
        )

        if len(filtered_emojis) == 0:
            await self.interaction.edit_original_response(
                content="Found no emoji matching your search term. Please try again.",
                view=RoleCreatorEmojiPickerView(
                    self.all_emojis,
                    self.all_emojis,
                    self.interaction,
                    self.callback,
                    self.result,
                ),
            )
            return

        await self.interaction.edit_original_response(
            content=f"Please pick a role emoji from the following list. Found `{len(filtered_emojis)}`.",
            view=RoleCreatorEmojiPickerView(
                self.all_emojis,
                filtered_emojis,
                self.interaction,
                self.callback,
                self.result,
            ),
        )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.blurple, row=2)
    async def confirm(self, interaction: Interaction, button: Button):
        self.stop()

        values = self.children[3].values

        if len(values) != 1:
            await interaction.response.send_message(
                "Please try again and choose exactly one emoji!",
                ephemeral=True,
                delete_after=self.DELETE_RESPONSE_AFTER,
            )
            return

        chosen_emoji_id = int(values[0])
        emoji = next(
            emoji for emoji in self.filtered_emojis if emoji.id == chosen_emoji_id
        )

        await self.complete_creation(interaction, emoji=emoji)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.red, row=2)
    async def skip(self, interaction: Interaction, button: Button):
        self.stop()
        await self.complete_creation(interaction, None)

    async def complete_creation(self, interaction, emoji=None):
        self.result.user_id = interaction.user.id
        self.result.emoji = emoji
        await self.callback(self.result)
        await interaction.response.send_message(
            "Your role has been created! <a:winterletsgo:1079552519971278959>",
            ephemeral=True,
            delete_after=self.DELETE_RESPONSE_AFTER,
        )


@role_setup_permission_check
class CustomRoleSetup(BaseView):
    def __init__(self):
        super().__init__()

        self.add_item(RolePicker())

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.blurple, row=2)
    async def confirm(self, interaction: Interaction, button: Button):
        self.stop()

        values = self.children[1].values

        if len(values) != 1:
            await interaction.response.send_message(
                "Please try again and choose exactly one role!",
                ephemeral=True,
                delete_after=self.DELETE_RESPONSE_AFTER,
            )
            return

        role = values[0]

        async with interaction.client.Session() as session:
            custom_role_settings = CustomRoleSettings(
                _role=role.id, _guild=interaction.guild_id
            )
            await session.merge(custom_role_settings)
            await session.commit()

            await interaction.response.send_message(
                f"Members with the role {role.mention} will now be able to create custom roles!",
                view=CustomRoleAnnouncementSetup(),
            )


@role_setup_permission_check
class CustomRoleAnnouncementSetup(BaseView):
    @discord.ui.button(
        label="Set up an announcement message", style=discord.ButtonStyle.blurple
    )
    async def set_announcement_message(self, interaction: Interaction, button: Button):
        await interaction.response.send_modal(CustomRoleAnnouncementTextModal())


class CustomRoleAnnouncementTextModal(
    BaseView, Modal, title="Set up an announcement message"
):
    msg = TextInput(
        label="Announcement message",
        placeholder="The announcement will be sent to the system channel.",
        required=False,
        min_length=0,
        max_length=255,
    )

    async def on_submit(self, interaction: Interaction) -> None:
        self.stop()

        # check if used placeholders are valid
        try:
            announcement_msg = format_template(self.msg.value, interaction.user)
        except commands.BadArgument as e:
            await interaction.response.send_message(e.args[0])
            return

        async with interaction.client.Session() as session:
            custom_role_settings = CustomRoleSettings(
                _guild=interaction.guild_id,
                _announcement_message=self.msg.value
                if len(self.msg.value) > 0
                else None,
            )
            await session.merge(custom_role_settings)
            await session.commit()

        await interaction.response.send_message(
            "Announcement message saved. Check the `placeholders` command for possible placeholders that will be "
            f"replaced in the announcement message. This is what the announcement will look like:\n{announcement_msg}",
            ephemeral=True,
            delete_after=self.DELETE_RESPONSE_AFTER,
        )


class RoleCreatorView(CallbackView, BaseView):
    @discord.ui.button(label="Click me to start", style=discord.ButtonStyle.blurple)
    async def create_role(self, interaction: Interaction, button: Button):
        self.result = RoleCreatorResult()
        await interaction.response.send_modal(
            RoleCreatorNameModal(self.callback, self.result)
        )

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if not await super().interaction_check(interaction):
            return False

        async with interaction.client.Session() as session:
            custom_role = await db.get_user_custom_role_in_guild(
                session, interaction.user.id, interaction.guild_id
            )

            if custom_role is not None:
                await interaction.response.send_message(
                    "You already have a custom role.",
                    ephemeral=True,
                    delete_after=self.DELETE_RESPONSE_AFTER,
                )
                return False

            custom_role_settings = await db.get_custom_role_settings(
                session, interaction.guild_id
            )
            member = interaction.guild.get_member(interaction.user.id)

            if member.guild_permissions.administrator or (
                custom_role_settings is not None
                and member is not None
                and custom_role_settings._role in [role.id for role in member.roles]
            ):
                return True

            await interaction.response.send_message(
                "You are missing a role to do this.",
                ephemeral=True,
                delete_after=self.DELETE_RESPONSE_AFTER,
            )
            return False


class RoleCreatorNameConfirmationView(CallbackView, BaseView):
    @discord.ui.button(label="I confirm", style=discord.ButtonStyle.blurple)
    async def confirm(self, interaction: Interaction, button: Button):
        role_name = self.result.name.strip()
        if interaction.client.contains_banned_word(role_name):
            await interaction.response.send_message(
                "Your role name contains a banned word.",
                ephemeral=True,
                delete_after=self.DELETE_RESPONSE_AFTER,
            )
            return

        self.stop()
        await interaction.response.send_modal(
            RoleCreatorColorModal(self.callback, self.result)
        )

    @discord.ui.button(label="Choose another name", style=discord.ButtonStyle.red)
    async def retry(self, interaction: Interaction, button: Button):
        self.stop()
        await interaction.response.send_modal(
            RoleCreatorNameModal(self.callback, self.result)
        )


class RoleCreatorEmojiSearchModal(
    Modal,
    title="Search for emojis by name",
):
    name = TextInput(
        label="Emoji name",
        placeholder="Enter a search term, e.g., seulgi",
        required=True,
    )

    def __init__(self):
        super().__init__()
        self.result = None

    async def on_submit(self, interaction: Interaction) -> None:
        self.result = self.name.value
        self.stop()
        await interaction.response.defer()


class RoleCreatorNameModal(
    CallbackView, BaseView, Modal, title="Choose your role's name"
):
    name = TextInput(
        label="Role name",
        placeholder="Your custom role name here...",
        required=True,
        min_length=2,
        max_length=20,
    )

    async def on_submit(self, interaction: Interaction) -> None:
        self.stop()
        self.result.name = self.name.value
        await interaction.response.send_message(
            f"Does your role name `{self.result.name}` abide by the server rules? "
            "If so, continue to role color selection.",
            view=RoleCreatorNameConfirmationView(self.callback, self.result),
            ephemeral=True,
            delete_after=self.DELETE_RESPONSE_AFTER,
        )


class RoleCreatorRetryColorView(CallbackView, BaseView):
    @discord.ui.button(label="Choose another color", style=discord.ButtonStyle.red)
    async def retry(self, interaction: Interaction, button: Button):
        self.stop()
        await interaction.response.send_modal(
            RoleCreatorColorModal(self.callback, self.result)
        )


class RoleCreatorColorConfirmationView(CallbackView, BaseView):
    @discord.ui.button(label="I confirm", style=discord.ButtonStyle.blurple)
    async def confirm(self, interaction: Interaction, button: Button):
        self.stop()
        await interaction.response.send_message(
            "Please pick a role emoji from the following list.",
            view=RoleCreatorEmojiPickerView(
                interaction.guild.emojis,
                interaction.guild.emojis,
                interaction,
                self.callback,
                self.result,
            ),
            ephemeral=True,
            delete_after=self.DELETE_RESPONSE_AFTER,
        )

    @discord.ui.button(label="Choose another color", style=discord.ButtonStyle.red)
    async def retry(self, interaction: Interaction, button: Button):
        self.stop()
        await interaction.response.send_modal(
            RoleCreatorColorModal(self.callback, self.result)
        )


class RoleCreatorColorModal(
    CallbackView, BaseView, Modal, title="Choose your role's color"
):
    color = TextInput(
        label="Role color",
        placeholder="000000",
        min_length=6,
        max_length=6,
    )

    async def on_submit(self, interaction: Interaction) -> None:
        self.stop()

        try:
            Color.from_str("#" + self.color.value)
        except ValueError:
            await interaction.response.send_message(
                "You entered an invalid color hex code. Please try again."
                f" {COLOR_PICKER_URL} might help to find a valid color.",
                view=RoleCreatorRetryColorView(self.callback, self.result),
                ephemeral=True,
                delete_after=self.DELETE_RESPONSE_AFTER,
            )
            return

        self.result.color = self.color.value
        await interaction.response.send_message(
            "Is your role color legible?",
            view=RoleCreatorColorConfirmationView(self.callback, self.result),
            ephemeral=True,
            delete_after=self.DELETE_RESPONSE_AFTER,
        )
