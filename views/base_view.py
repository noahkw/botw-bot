from discord import Interaction
from discord.ui import View


class BaseView(View):
    """
    Has to be called and checked by extending classes.
    I.e., if False, the interaction_check has to fail
    """

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        return not interaction.client.is_author_blocked_in_guild(
            interaction.user, interaction.guild
        )
