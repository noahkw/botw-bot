import asyncio
import typing

import discord
from discord import Interaction, Button, Color
from discord.ui import TextInput, Modal, RoleSelect

import db
from const import COLOR_PICKER_URL

from models import CustomRoleSettings
from views.base_view import BaseView


class RoleCreatorResult:
    name: str
    color: str
    user_id: int

    def __init__(self):
        self.name = None
        self.color = None
        self.user_id = None


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

    async def callback(self, interaction: Interaction) -> typing.Any:
        role = self.values[0]
        client_member = interaction.guild.get_member(interaction.client.user.id)
        if role.position >= client_member.top_role.position:
            await interaction.response.send_message(
                "Please choose a role the bot can manage, i.e., one that is below its own highest role.",
                ephemeral=True,
                delete_after=120.0,
            )

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
        self.result.user_id = interaction.user.id
        await self.callback(self.result)
        await interaction.response.send_message(
            "Your role has been created! <a:winterletsgo:1079552519971278959>",
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
