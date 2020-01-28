

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
