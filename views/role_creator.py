import discord
from discord import Interaction, Button
from discord.ui import View, TextInput, Modal


class RoleCreatorView(View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Click me to start", style=discord.ButtonStyle.blurple)
    async def create_role(self, interaction: Interaction, button: Button):
        await interaction.response.send_modal(RoleCreatorNameModal())


class RoleCreatorNameConfirmationView(View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="I confirm", style=discord.ButtonStyle.blurple)
    async def confirm(self, interaction: Interaction, button: Button):
        await interaction.response.send_modal(RoleCreatorColorModal())

    @discord.ui.button(label="Choose another name", style=discord.ButtonStyle.red)
    async def retry(self, interaction: Interaction, button: Button):
        await interaction.response.send_modal(RoleCreatorNameModal())


class RoleCreatorNameModal(Modal, title="Choose your role's name"):
    name = TextInput(
        label="Role name",
        placeholder="Your custom role name here...",
        required=True,
        min_length=3,
        max_length=20,
    )

    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.send_message(
            "Does your role name abide by the server rules? "
            "If so, continue to role color selection.",
            view=RoleCreatorNameConfirmationView(),
            ephemeral=True,
        )


class RoleCreatorColorConfirmationView(View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="I confirm.", style=discord.ButtonStyle.blurple)
    async def confirm(self, interaction: Interaction, button: Button):
        await interaction.response.send_message(
            "Your role has been created! <a:winterletsgo:1079552519971278959>",
            ephemeral=True,
        )

    @discord.ui.button(label="Choose another color", style=discord.ButtonStyle.red)
    async def retry(self, interaction: Interaction, button: Button):
        await interaction.response.send_modal(RoleCreatorColorModal())


class RoleCreatorColorModal(Modal, title="Choose your role's color"):
    color = TextInput(
        label="Role color",
        placeholder="000000",
        min_length=6,
        max_length=6,
    )

    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.send_message(
            "Is your role color legible?",
            view=RoleCreatorColorConfirmationView(),
            ephemeral=True,
        )
