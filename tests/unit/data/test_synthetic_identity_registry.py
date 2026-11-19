"""Verify transactional identity allocation and audit lineage."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from nowa_customer_intelligence.data.synthetic.identity_registry import (
    EpisodeIdentity,
    EpisodeIdentityRegistry,
    IdentityConflict,
)

_FIRST = EpisodeIdentity("fictional-client", "baseline", "episode-one", "establishment-1")
_SECOND = replace(_FIRST, source_key="episode-two", establishment_ref="establishment-2")


def test_registry_reuse_and_isolation_survive_reopening(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    registry = EpisodeIdentityRegistry(path)
    assert registry.lookup(_FIRST) is None
    original, second = registry.allocate_many((_FIRST, _SECOND))
    assert original != second and UUID(original).version == 4
    assert registry.allocate_many((_FIRST,)) == (original,)
    reopened = EpisodeIdentityRegistry(path)
    assert reopened.lookup(_FIRST) == original
    isolated = replace(_FIRST, client="other-fictional-client")
    another_namespace = replace(_FIRST, namespace="another-scenario")
    assert reopened.lookup(isolated) is None
    assert reopened.lookup(another_namespace) is None
    assert len({original, *reopened.allocate_many((isolated, another_namespace))}) == 3
    reopened.verify_many(((_FIRST, original),))
    with pytest.raises(IdentityConflict, match="unavailable"):
        reopened.verify_many(((_FIRST, second),))


def test_duplicate_uuid_and_interruption_roll_back_the_whole_batch(tmp_path: Path) -> None:
    identifier = uuid4()
    registry = EpisodeIdentityRegistry(
        tmp_path / "registry.sqlite", uuid_factory=lambda: identifier
    )
    with pytest.raises(IdentityConflict, match="already allocated"):
        registry.allocate_many((_FIRST, _SECOND))
    assert registry.lookup(_FIRST) is None
    assert registry.history(client=_FIRST.client, namespace=_FIRST.namespace) == ()

    def interrupted():
        yield _FIRST
        raise RuntimeError("interrupted test transaction")

    with pytest.raises(RuntimeError, match="interrupted"):
        registry.allocate_many(interrupted())
    assert registry.lookup(_FIRST) is None
    assert registry.allocate_many((_FIRST,)) == (str(identifier),)
    registry = EpisodeIdentityRegistry(tmp_path / "registry.sqlite")
    with pytest.raises(IdentityConflict, match="conflicts"):
        registry.allocate_many((_SECOND, replace(_FIRST, establishment_ref="different-fact")))
    assert registry.lookup(_SECOND) is None


def test_explicit_key_correction_preserves_lineage_without_alias_guessing(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    registry = EpisodeIdentityRegistry(path)
    canonical, _ = registry.allocate_many((_FIRST, _SECOND))
    with pytest.raises(IdentityConflict, match="unused"):
        registry.correct_source_key(
            _FIRST, _SECOND.source_key, reason="explicit fixture correction"
        )
    corrected = registry.correct_source_key(_FIRST, "revised-key", reason="fixture key amendment")
    reopened = EpisodeIdentityRegistry(path)
    assert reopened.lookup(corrected) == canonical
    with pytest.raises(IdentityConflict, match="retired"):
        reopened.lookup(_FIRST)
    records = reopened.history(client=_FIRST.client, namespace=_FIRST.namespace)
    assert len(records) == 3
    assert records[0].subscription_id == records[-1].subscription_id == canonical
    assert records[-1].source_key == _FIRST.source_key
    assert records[-1].replacement_key == "revised-key"
    assert reopened.history(client="other-client", namespace=_FIRST.namespace) == ()


def test_rejects_symlink_and_invalid_uuid_provider(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    pointer = tmp_path / "pointer.sqlite"
    pointer.symlink_to(path)
    with pytest.raises(IdentityConflict, match="explicit local"):
        EpisodeIdentityRegistry(pointer)
    with pytest.raises(IdentityConflict, match="bounded"):
        replace(_FIRST, client=" ")
    registry = EpisodeIdentityRegistry(path, uuid_factory=lambda: UUID(int=0))
    with pytest.raises(IdentityConflict, match="UUID4"):
        registry.allocate_many((_FIRST,))
    assert registry.lookup(_FIRST) is None


def test_registry_rejects_rebinding_the_same_establishment_without_correction(
    tmp_path: Path,
) -> None:
    registry = EpisodeIdentityRegistry(tmp_path / "registry.sqlite")
    (original,) = registry.allocate_many((_FIRST,))
    ambiguous = replace(_FIRST, source_key="other-key-with-same-evidence")
    with pytest.raises(IdentityConflict, match="already has a source mapping"):
        registry.allocate_many((ambiguous,))
    assert registry.lookup(ambiguous) is None
    assert registry.lookup(_FIRST) == original


def test_concurrent_requests_allocate_the_same_identity_once(tmp_path: Path) -> None:
    registry = EpisodeIdentityRegistry(tmp_path / "registry.sqlite")
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(registry.allocate_many, (_FIRST,))
        second = executor.submit(registry.allocate_many, (_FIRST,))
        assert first.result() == second.result()
    assert len(registry.history(client=_FIRST.client, namespace=_FIRST.namespace)) == 1
