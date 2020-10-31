import io
import logging
import textwrap

from PIL import Image, ImageFont
from discord import File
from discord.ext import commands

from util import draw_rotated_text

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Fun(bot))


class Fun(commands.Cog):
    ARIAL_FONT_PATH = r"data/fonts/ArialMdm.ttf"
    SWANTF_IMG_PATH = r"data/image_templates/swantf.jpg"
    SWANTF_MAX_CHARS = 150

    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        aliases=["m", "meme"],
        brief="Create meme images/videos",
        invoke_without_command=True,
    )
    async def memes(self, ctx):
        await ctx.send_help(self.memes)

    def make_swantf_image(self, text):
        with open(self.SWANTF_IMG_PATH, "rb") as f:
            template = Image.open(f)

            font = ImageFont.truetype(
                font=self.ARIAL_FONT_PATH, size=38, encoding="unic"
            )

            # wrap text
            text = textwrap.fill(text, width=20)

            draw_rotated_text(template, 26.0, (65, 1200), text, (0, 0, 0), font=font)

            buffer = io.BytesIO()
            template.save(buffer, "jpeg")
            buffer.seek(0)

            return buffer

    @memes.command(brief="Creates meme image from Trump/Swan interview template")
    async def swantf(self, ctx, *, text: commands.clean_content):
        if len(text) >= self.SWANTF_MAX_CHARS:
            raise commands.BadArgument(
                f"Text too long. Must be less than {self.SWANTF_MAX_CHARS} characters."
            )

        with ctx.typing():
            image_buffer = await self.bot.loop.run_in_executor(
                None, self.make_swantf_image, text
            )
            await ctx.send(file=File(image_buffer, filename="swan_tf.jpg"))
