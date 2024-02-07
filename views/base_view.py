from discord import Interaction
from discord.ui import View


class BaseView(View):
    DELETE_RESPONSE_AFTER = 120.0

    def __init__(self):
        super().__init__()
        self.timeout = 120.0

    """
    Has to be called and checked by extending classes.
    I.e., if False, the interaction_check has to fail
    """

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        return not interaction.client.is_author_blocked_in_guild(
            interaction.user, interaction.guild
        )
