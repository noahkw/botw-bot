import asyncio
import logging
import re

import discord
from discord.ext import commands

from const import CHECK_EMOJI

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(CardGameUtils(bot))


class CardGameUtilsNotEnabled(commands.CheckFailure):
    pass


def card_game_utils_enabled():
    async def predicate(ctx):
        enabled_guilds = ctx.bot.config["cogs"]["cardgameutils"]["enabled_guilds"]
        if ctx.guild.id not in enabled_guilds:
            raise CardGameUtilsNotEnabled
        else:
            return True

    return commands.check(predicate)


class CardGameUtils(commands.Cog):
    CARD_CODE_REGEX = r"Code: ([A-Z0-9]{4})"
    CARD_IV_REGEX = r"\(IV: ([0-9]0?)\)"
    CARD_STAR_REGEX = r":star:"
    CARD_COLLECTION_VAULT_REGEX = r"(:gem:|:lock:)"
    CARD_PAGE_REGEX = r"([0-9]+)/([0-9]*) pages"

    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if hasattr(ctx.command, "on_error"):
            return

        if isinstance(error, CardGameUtilsNotEnabled):
            await ctx.send("Card Game Utils have not been enabled in this server.")
        else:
            logger.exception(error)

    def _get_page(self, footer):
        result = re.search(self.CARD_PAGE_REGEX, footer)
        if result:
            return result.group(1), result.group(2)

    @commands.command()
    @card_game_utils_enabled()
    async def fodder(
        self, ctx, message: discord.Message, max_iv: int = 9, max_rank: int = 4
    ):
        if not len(message.embeds) == 1 or "cards" not in message.embeds[0].author.name:
            raise commands.BadArgument("Pass the inventory embed's message ID.")

        prompt = await ctx.send(
            "Starting fodder scraping session...\n"
            "Go through the pages and click the reaction when you are done."
        )
        await prompt.add_reaction(CHECK_EMOJI)

        prev_page = ()
        cards = []
        stop = [False]

        def check(reaction, user):
            return user == ctx.author and reaction.message == prompt

        async def stop_task():
            try:
                await self.bot.wait_for("reaction_add", check=check, timeout=5 * 60.0)
            except asyncio.TimeoutError:
                stop[0] = True

            stop[0] = True

        asyncio.create_task(stop_task())

        while True:
            message = await ctx.channel.fetch_message(message.id)
            curr_page = self._get_page(message.embeds[0].footer.text)

            if curr_page != prev_page:
                cards.extend(
                    [(field.name, field.value) for field in message.embeds[0].fields]
                )

            await asyncio.sleep(1)

            if stop[0]:
                break

            prev_page = curr_page

        codes = set()

        for name, value in cards:
            iv = re.search(self.CARD_IV_REGEX, value, flags=re.DOTALL)
            stars = re.findall(self.CARD_STAR_REGEX, value, flags=re.DOTALL)
            code = re.search(self.CARD_CODE_REGEX, value, flags=re.DOTALL)
            collection_or_vault = re.search(
                self.CARD_COLLECTION_VAULT_REGEX, name, flags=re.DOTALL
            )

            if (
                not collection_or_vault
                and iv
                and int(iv.group(1)) <= max_iv
                and len(stars) <= max_rank
            ):
                codes.add(code.group(1))

        await ctx.send(f"Fodder codes:\n```{' '.join(codes)}```")
