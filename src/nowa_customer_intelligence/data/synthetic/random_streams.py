"""Versioned, local random streams for synthetic development."""

from hashlib import sha256
from re import compile

from numpy.random import PCG64, Generator

STREAM_ALGORITHM = "numpy.PCG64+sha256/nci-stream-v1"
_DOMAIN = b"nowa.synthetic.stream.v1\0"
_NAME = compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*")
_MAX_SEED = 2**63 - 1


class RandomStreamError(ValueError):
    """A stream declaration is invalid."""


def create_random_stream(master_seed: int, name: str, *, namespace: str = "default") -> Generator:
    """Return a fresh PCG64 generator for this seed, namespace and name.

    Derive entropy from SHA-256 over the version domain, eight unsigned
    big-endian seed bytes, the ASCII namespace, NUL and the ASCII name.
    """
    if type(master_seed) is not int or not 0 <= master_seed <= _MAX_SEED:
        raise RandomStreamError("Expected a master seed from 0 through 2**63 - 1.")
    for label in (name, namespace):
        if type(label) is not str or len(label) > 256 or not _NAME.fullmatch(label):
            raise RandomStreamError("Expected a valid stream name and namespace.")
    payload = (
        _DOMAIN
        + master_seed.to_bytes(8, "big")
        + namespace.encode("ascii")
        + b"\0"
        + name.encode("ascii")
    )
    entropy = int.from_bytes(sha256(payload).digest(), "big")
    return Generator(PCG64(entropy))
