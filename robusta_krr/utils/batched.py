import itertools
from typing import Iterable, TypeVar

_T = TypeVar("_T")


def batched(iterable: Iterable[_T], n: int) -> Iterable[list[_T]]:
    "Batch data into tuples of length n. The last batch may be shorter."
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := list(itertools.islice(it, n)):
        yield batch
