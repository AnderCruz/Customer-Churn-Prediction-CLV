"""Local identity persistence for explicitly established fictional episodes."""

import sqlite3
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4


class IdentityConflict(ValueError):
    """An identity request lacks unambiguous authoritative evidence."""


def _identifier(value: str) -> bool:
    return type(value) is str and 0 < len(value) <= 256 and value == value.strip()


@dataclass(frozen=True, slots=True)
class EpisodeIdentity:
    """A caller-attested source episode within an explicit client and namespace."""

    client: str
    namespace: str
    source_key: str
    establishment_ref: str

    def __post_init__(self) -> None:
        if not all(
            _identifier(value)
            for value in (self.client, self.namespace, self.source_key, self.establishment_ref)
        ):
            raise IdentityConflict("Expected explicit bounded source identity and evidence.")


@dataclass(frozen=True, slots=True)
class MappingChange:
    """An append-only allocation or correction audit entry."""

    source_key: str
    replacement_key: str | None
    subscription_id: str
    reason: str


class EpisodeIdentityRegistry:
    """Transactional, caller-located SQLite store for development identities."""

    def __init__(self, path: Path, *, uuid_factory: Callable[[], UUID] = uuid4) -> None:
        if not isinstance(path, Path) or not path.parent.is_dir() or path.is_symlink():
            raise IdentityConflict("Expected an explicit local registry file path.")
        self._path = path
        self._uuid_factory = uuid_factory
        with self._transaction() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS episode_mapping (
                    client TEXT NOT NULL, namespace TEXT NOT NULL, source_key TEXT NOT NULL,
                    evidence TEXT NOT NULL, subscription_id TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK (active IN (0, 1)),
                    PRIMARY KEY (client, namespace, source_key)
                )
            """)
            db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS active_episode_uuid
                ON episode_mapping(subscription_id) WHERE active = 1
            """)
            db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS active_establishment
                ON episode_mapping(client, namespace, evidence) WHERE active = 1
            """)
            db.execute(
                "CREATE INDEX IF NOT EXISTS episode_uuid_history "
                "ON episode_mapping(subscription_id)"
            )
            db.execute("""
                CREATE TABLE IF NOT EXISTS mapping_audit (
                    id INTEGER PRIMARY KEY, client TEXT NOT NULL, namespace TEXT NOT NULL,
                    source_key TEXT NOT NULL, replacement_key TEXT, subscription_id TEXT NOT NULL,
                    reason TEXT NOT NULL
                )
            """)

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self._path, isolation_level=None)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _mapping(db: sqlite3.Connection, identity: EpisodeIdentity) -> tuple[str, str, int] | None:
        return db.execute(
            "SELECT evidence, subscription_id, active FROM episode_mapping "
            "WHERE client = ? AND namespace = ? AND source_key = ?",
            (identity.client, identity.namespace, identity.source_key),
        ).fetchone()

    @staticmethod
    def _check_existing(row: tuple[str, str, int], identity: EpisodeIdentity) -> str:
        evidence, identifier, active = row
        if not active or evidence != identity.establishment_ref:
            raise IdentityConflict(
                "Source identity is retired or conflicts with recorded evidence."
            )
        return identifier

    def lookup(self, identity: EpisodeIdentity) -> str | None:
        """Return the active mapping only if its evidence agrees."""
        with self._transaction() as db:
            row = self._mapping(db, identity)
            return self._check_existing(row, identity) if row is not None else None

    def verify_many(self, expected: Iterable[tuple[EpisodeIdentity, str]]) -> None:
        """Verify existing allocations without allocating missing identities."""
        with self._transaction() as db:
            for identity, identifier in expected:
                row = self._mapping(db, identity)
                if row is None or self._check_existing(row, identity) != identifier:
                    raise IdentityConflict("An expected allocation is unavailable or conflicts.")

    def allocate_many(self, identities: Iterable[EpisodeIdentity]) -> tuple[str, ...]:
        """Allocate or reuse identities atomically in the caller's input order."""
        results = []
        try:
            with self._transaction() as db:
                for identity in identities:
                    row = self._mapping(db, identity)
                    if row is not None:
                        results.append(self._check_existing(row, identity))
                        continue
                    if (
                        db.execute(
                            "SELECT 1 FROM episode_mapping "
                            "WHERE client = ? AND namespace = ? AND evidence = ? AND active = 1",
                            (identity.client, identity.namespace, identity.establishment_ref),
                        ).fetchone()
                        is not None
                    ):
                        raise IdentityConflict(
                            "Establishment evidence already has a source mapping."
                        )
                    supplied = self._uuid_factory()
                    if type(supplied) is not UUID or supplied.version != 4:
                        raise IdentityConflict("The allocation provider must return UUID4.")
                    identifier = str(supplied)
                    if (
                        db.execute(
                            "SELECT 1 FROM episode_mapping WHERE subscription_id = ?", (identifier,)
                        ).fetchone()
                        is not None
                    ):
                        raise IdentityConflict("Canonical identifier was already allocated.")
                    db.execute(
                        "INSERT INTO episode_mapping VALUES (?, ?, ?, ?, ?, 1)",
                        (
                            identity.client,
                            identity.namespace,
                            identity.source_key,
                            identity.establishment_ref,
                            identifier,
                        ),
                    )
                    db.execute(
                        "INSERT INTO mapping_audit "
                        "(client, namespace, source_key, subscription_id, reason) "
                        "VALUES (?, ?, ?, ?, 'allocated')",
                        (identity.client, identity.namespace, identity.source_key, identifier),
                    )
                    results.append(identifier)
        except sqlite3.IntegrityError:
            raise IdentityConflict("The allocation conflicts with stored identity.") from None
        return tuple(results)

    def correct_source_key(
        self, prior: EpisodeIdentity, replacement_key: str, *, reason: str
    ) -> EpisodeIdentity:
        """Move a source key explicitly, retaining its canonical ID and retired lineage."""
        if not _identifier(reason):
            raise IdentityConflict("Expected a bounded correction reason.")
        replacement = EpisodeIdentity(
            prior.client, prior.namespace, replacement_key, prior.establishment_ref
        )
        with self._transaction() as db:
            row = self._mapping(db, prior)
            if row is None or self._mapping(db, replacement) is not None:
                raise IdentityConflict("Correction requires an existing and an unused source key.")
            identifier = self._check_existing(row, prior)
            db.execute(
                "UPDATE episode_mapping SET active = 0 "
                "WHERE client = ? AND namespace = ? AND source_key = ?",
                (prior.client, prior.namespace, prior.source_key),
            )
            db.execute(
                "INSERT INTO episode_mapping VALUES (?, ?, ?, ?, ?, 1)",
                (
                    replacement.client,
                    replacement.namespace,
                    replacement.source_key,
                    replacement.establishment_ref,
                    identifier,
                ),
            )
            db.execute(
                "INSERT INTO mapping_audit "
                "(client, namespace, source_key, replacement_key, subscription_id, reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    prior.client,
                    prior.namespace,
                    prior.source_key,
                    replacement_key,
                    identifier,
                    reason,
                ),
            )
        return replacement

    def history(self, *, client: str, namespace: str) -> tuple[MappingChange, ...]:
        """Read the allocation and correction lineage for an explicit source scope."""
        if not _identifier(client) or not _identifier(namespace):
            raise IdentityConflict("Expected an explicit client and source namespace.")
        with self._transaction() as db:
            rows = db.execute(
                "SELECT source_key, replacement_key, subscription_id, reason FROM mapping_audit "
                "WHERE client = ? AND namespace = ? ORDER BY id",
                (client, namespace),
            )
            return tuple(MappingChange(*row) for row in rows)
