import asyncio
import logging
import re
import subprocess
import typing
from random import getrandbits

import discord
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


def chunker(iterable, n, return_index=False):
    """
    Produces a generator that yields chunks of given size from an iterator.
    :param iterable: iterable to generate chunks from
    :param n: number of items in each chunk
    :param return_index: set to true if first yielded value should be the chunk's starting index
    :return: the individual chunks
    """
    for i in range(0, len(iterable), n):
        if return_index:
            yield i, iterable[i : i + n]
        else:
            yield iterable[i : i + n]


def ordered_sublists(superlist, n):
    """
    Produces a generator that yields all ordered sublists of length n
    :param superlist: The list to generate sublists from
    :param n: Length of the sublists
    :return: the individual sublists
    """
    for i in range(0, len(superlist) - n + 1):
        yield superlist[i : i + n]


def random_bool():
    return bool(getrandbits(1))


def mock_case(msg):
    return "".join([c.swapcase() if random_bool() else c for c in msg])


def remove_broken_emoji(msg):
    return re.sub(r"<(a)*:[\w]+:([0-9]+)>( )*", "", msg)


def has_passed(date):
    import pendulum

    return date.timestamp() < pendulum.now("UTC").timestamp()


def celsius_to_fahrenheit(temp):
    return temp * (9 / 5) + 32


def meters_to_miles(meters):
    return meters * 0.000621371


class Cooldown:
    def __init__(self, duration):
        self.cooldown = False
        self.duration = duration

    async def __aenter__(self):
        self.cooldown = True
        await asyncio.sleep(self.duration)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.cooldown = False


def flatten(list_):
    return [item for sublist in list_ for item in sublist]


def git_version_label():
    return (
        subprocess.check_output(["git", "describe", "--tags", "--long"])
        .decode("ascii")
        .strip()
    )


def git_short_history(n):
    return (
        subprocess.check_output(
            ["git", "log", f"-{n}", "--pretty=format:`%h`: %s (%ar)"]
        )
        .decode("ascii")
        .strip()
    )


def draw_rotated_text(image, angle, xy, text, fill, *args, **kwargs):
    """Draw text at an angle into an image, takes the same arguments
        as Image.text() except for:

    :param image: Image to write text into
    :param angle: Angle to write text at
    """
    # get the size of our image
    width, height = image.size
    max_dim = max(width, height)

    # build a transparency mask large enough to hold the text
    mask_size = (max_dim * 2, max_dim * 2)
    mask = Image.new("L", mask_size, 0)

    # add text to mask
    draw = ImageDraw.Draw(mask)
    draw.text((max_dim, max_dim), text, 255, *args, **kwargs)

    if angle % 90 == 0:
        # rotate by multiple of 90 deg is easier
        rotated_mask = mask.rotate(angle)
    else:
        # rotate an an enlarged mask to minimize jaggies
        bigger_mask = mask.resize((max_dim * 4, max_dim * 4), resample=Image.BICUBIC)
        rotated_mask = bigger_mask.rotate(angle).resize(
            mask_size, resample=Image.LANCZOS
        )

    # crop the mask to match image
    mask_xy = (max_dim - xy[0], max_dim - xy[1])
    b_box = mask_xy + (mask_xy[0] + width, mask_xy[1] + height)
    mask = rotated_mask.crop(b_box)

    # paste the appropriate color, with the text transparency mask
    color_image = Image.new("RGBA", image.size, fill)
    image.paste(color_image, mask)


def safe_mention(obj: typing.Union[discord.Member, discord.User, discord.TextChannel]):
    if obj:
        return obj.mention
    else:
        return "*Unknown*"


async def safe_send(
    dest: typing.Optional[discord.abc.Messageable], content: str
) -> typing.Optional[discord.Message]:
    # So far, this function just attempts to send the message to given user and logs a message if
    # a 403 Forbidden was caught.
    if dest is None:
        return

    try:
        return await dest.send(content)
    except discord.Forbidden:
        logger.info(
            "Could not message entity with ID %d", (await dest._get_channel()).id
        )


def format_emoji(emoji: discord.Emoji):
    return f"{emoji} `{emoji.name}`"


def detail_mention(obj: discord.Object, id: typing.Optional[int] = None):
    # try:
    try:
        mention = safe_mention(obj)
    except AttributeError:
        mention = ""

    try:
        id_ = f"(`{obj.id}`)"
    except AttributeError:
        id_ = f"(`{id}`)" or ""

    return f"{mention} {str(obj)} {id_}"
