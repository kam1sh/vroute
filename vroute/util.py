import itertools
import re
import typing as ty


def chunked(iterable, size):
    args = [iter(iterable)] * size
    return itertools.zip_longest(*args, fillvalue=None)


T = ty.TypeVar("T")

class WindowIterator:
    """
    Iterator with extras attributes, such as
    `first`, `last`, `pos` and `has_any`.
    """

    def __init__(self, iterable: ty.Iterable[T]):
        self._gen = enumerate(iterable)
        self._buf: ty.List[T] = []
        self._ended = False
        self.pos = None
        self.fetch()

    def fetch(self):
        try:
            val = next(self._gen)
            self._buf.append(val)
        except StopIteration:
            pass

    def __iter__(self):
        return self

    def __next__(self):
        self.fetch()
        if self._ended or not self._buf:
            raise StopIteration
        self.pos, val = self._buf.pop(0)
        return val

    @property
    def last(self):
        return not self._buf

    @property
    def first(self):
        return self.pos == 0

    @property
    def has_any(self):
        return bool(self._buf)


ipv4_regex = re.compile(r"([\d.]+)(/\d+)?")


def with_netmask(address) -> str:
    if not isinstance(address, str):
        address = str(address)
    match = ipv4_regex.match(address)
    if not match:
        raise ValueError(address)
    addr = match.group(1)
    netmask = match.group(2) or "/32"
    return addr + netmask
