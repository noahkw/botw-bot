import asyncio
import re
import subprocess
from random import getrandbits


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
            yield i, iterable[i:i + n]
        else:
            yield iterable[i:i + n]


def ordered_sublists(superlist, n):
    """
    Produces a generator that yields all ordered sublists of length n
    :param superlist: The list to generate sublists from
    :param n: Length of the sublists
    :return: the individual sublists
    """
    for i in range(0, len(superlist) - n + 1):
        yield superlist[i:i + n]


def random_bool():
    return bool(getrandbits(1))


def mock_case(msg):
    return ''.join([c.swapcase() if random_bool() else c for c in msg])


def remove_broken_emoji(msg):
    return re.sub(r'<(a)*:[\w]+:([0-9]+)>( )*', '', msg)


def has_passed(date):
    import pendulum
    return date.timestamp() < pendulum.now('UTC').timestamp()


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


def flatten(l):
    return [item for sublist in l for item in sublist]


def git_version_label():
    return subprocess.check_output(['git', 'describe', '--tags', '--long']).decode('ascii').strip()
