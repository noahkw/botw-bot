import typing

import discord
from discord import Interaction, Button
from discord.ui import View, TextInput, Modal

import db


class RoleCreatorResult:
    name: str | None
    color: str | None
    user_id: int | None

    def __init__(self):
        self.name = None
        self.color = None
        self.user_id = None


class CallbackView:
    callback: typing.Callable[[typing.Any], typing.Awaitable[typing.Any]]
    result: RoleCreatorResult

    def __init__(self, callback, result):
        super().__init__()
        self.callback = callback
        self.result = result


class RoleCreatorView(CallbackView, View):
    @discord.ui.button(label="Click me to start", style=discord.ButtonStyle.blurple)
    async def create_role(self, interaction: Interaction, button: Button):
        self.result = RoleCreatorResult()
        await interaction.response.send_modal(
            RoleCreatorNameModal(self.callback, self.result)
        )

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        async with interaction.client.Session() as session:
            custom_role = await db.get_user_custom_role_in_guild(
                session, interaction.user.id, interaction.guild_id
            )

            if custom_role is not None:
                await interaction.response.send_message(
                    "You already have a custom role.", ephemeral=True
                )
                return False

        # FIXME remove me!
        return True

        if (
            interaction.user.premium_since is None
            and not interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                "You are not a server booster.", ephemeral=True
            )
            return False

        return True


class RoleCreatorNameConfirmationView(CallbackView, View):
    @discord.ui.button(label="I confirm", style=discord.ButtonStyle.blurple)
    async def confirm(self, interaction: Interaction, button: Button):
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


class RoleCreatorNameModal(CallbackView, Modal, title="Choose your role's name"):
    name = TextInput(
        label="Role name",
        placeholder="Your custom role name here...",
        required=True,
        min_length=3,
        max_length=20,
    )

    async def on_submit(self, interaction: Interaction) -> None:
        self.stop()
        self.result.name = self.name.value
        await interaction.response.send_message(
            "Does your role name abide by the server rules? "
            "If so, continue to role color selection.",
            view=RoleCreatorNameConfirmationView(self.callback, self.result),
            ephemeral=True,
        )


class RoleCreatorColorConfirmationView(CallbackView, View):
    @discord.ui.button(label="I confirm", style=discord.ButtonStyle.blurple)
    async def confirm(self, interaction: Interaction, button: Button):
        self.stop()
        self.result.user_id = interaction.user.id
        await self.callback(self.result)
        await interaction.response.send_message(
            "Your role has been created! <a:winterletsgo:1079552519971278959>",
            ephemeral=True,
        )

    @discord.ui.button(label="Choose another color", style=discord.ButtonStyle.red)
    async def retry(self, interaction: Interaction, button: Button):
        self.stop()
        await interaction.response.send_modal(
            RoleCreatorColorModal(self.callback, self.result)
        )


class RoleCreatorColorModal(CallbackView, Modal, title="Choose your role's color"):
    color = TextInput(
        label="Role color",
        placeholder="000000",
        min_length=6,
        max_length=6,
    )

    async def on_submit(self, interaction: Interaction) -> None:
        self.stop()
        self.result.color = self.color.value
        await interaction.response.send_message(
            "Is your role color legible?",
            view=RoleCreatorColorConfirmationView(self.callback, self.result),
            ephemeral=True,
        )
