"""Verify stream derivation, replay and process state isolation."""

import random

import numpy as np
import pytest

from nowa_customer_intelligence.data.synthetic.random_streams import (
    STREAM_ALGORITHM,
    RandomStreamError,
    create_random_stream,
)


def test_streams_replay_independently_of_creation_order() -> None:
    first = create_random_stream(42, "customer.created-at")
    other = create_random_stream(42, "usage")
    expected = first.integers(0, 1_000_000, size=12)
    assert not np.array_equal(expected, other.integers(0, 1_000_000, size=12))
    other.integers(0, 100, size=100)
    replay = create_random_stream(42, "customer.created-at")
    assert replay is not first
    np.testing.assert_array_equal(replay.integers(0, 1_000_000, size=12), expected)
    assert not np.array_equal(
        create_random_stream(43, "customer.created-at").integers(0, 1_000_000, size=12),
        expected,
    )


def test_namespace_separates_designated_streams() -> None:
    first = create_random_stream(0, "customer", namespace="baseline")
    second = create_random_stream(0, "customer", namespace="growth")
    assert first.bit_generator.state != second.bit_generator.state


@pytest.mark.parametrize("seed", [-1, 2**63, True, "42"])
def test_rejects_invalid_seeds(seed: int) -> None:
    with pytest.raises(RandomStreamError, match="master seed"):
        create_random_stream(seed, "customer")


@pytest.mark.parametrize("name", ["", "UPPER", "a..b", "a\0b", "a" * 257, "aé", None])
def test_rejects_invalid_names_safely(name: str) -> None:
    with pytest.raises(RandomStreamError, match="stream name and namespace"):
        create_random_stream(0, name)
    with pytest.raises(RandomStreamError, match="stream name and namespace"):
        create_random_stream(0, "customer", namespace=name)


def test_preserves_python_and_numpy_global_state() -> None:
    before_python = random.getstate()
    before_numpy = np.random.get_state()
    assert STREAM_ALGORITHM == "numpy.PCG64+sha256/nci-stream-v1"
    create_random_stream(2**63 - 1, "a" * 256).bit_generator.random_raw(20)
    assert random.getstate() == before_python
    after_numpy = np.random.get_state()
    assert after_numpy[0] == before_numpy[0]
    np.testing.assert_array_equal(after_numpy[1], before_numpy[1])
    assert after_numpy[2:] == before_numpy[2:]


def test_v1_derivation_vector() -> None:
    stream = create_random_stream(42, "customer.created-at", namespace="baseline.v1")
    assert stream.bit_generator.random_raw(3).tolist() == [
        12461106456922106221,
        11892388689380006372,
        11672909643144480393,
    ]
