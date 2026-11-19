"""Test byte integrity evidence independently from generator execution."""

import csv
from hashlib import sha256
from pathlib import Path

from nowa_customer_intelligence.data.synthetic.projection import ProjectedDataset
from nowa_customer_intelligence.data.synthetic.provenance import (
    DatasetInventory,
    capture_development_integrity,
    verify_development_integrity,
)


def test_counts_records_not_physical_lines_and_keeps_evidence_refs(tmp_path: Path) -> None:
    table = ProjectedDataset(
        "customers",
        ("customer_id", "created_at", "industry"),
        (("synthetic-1", "2024-01-01", "fictional,\nindustry"),),
    )
    path = tmp_path / "customers.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(table.columns)
        writer.writerows(table.rows)
    original = path.read_bytes()
    evidence = capture_development_integrity(
        tmp_path, (table,), inventory=(DatasetInventory("customers", 1, ("validation-1",)),)
    )
    (entry,) = evidence.files
    assert evidence.passed
    assert entry.records == 1
    assert entry.size_bytes == len(original)
    assert entry.sha256_hex == sha256(original).hexdigest()
    assert entry.validation_refs == ("validation-1",)
    assert verify_development_integrity(tmp_path, evidence) == evidence
    assert path.read_bytes() == original


def test_invalid_csv_capture_cannot_become_accepted_by_later_byte_verification(
    tmp_path: Path,
) -> None:
    table = ProjectedDataset("customers", ("customer_id",), (("synthetic-1",),))
    path = tmp_path / "customers.csv"
    path.write_bytes(b'customer_id\n"unterminated\n')
    rejected = capture_development_integrity(tmp_path, (table,))
    assert rejected.files[0].problem == "invalid_csv"
    assert not verify_development_integrity(tmp_path, rejected).passed


def test_integrity_rejects_invalid_inventory_and_missing_directory(tmp_path: Path) -> None:
    unknown = ProjectedDataset("../outside", (), ())
    assert (
        capture_development_integrity(tmp_path, (unknown,)).directory_problem == "invalid_inventory"
    )
    table = ProjectedDataset("customers", ("customer_id",), ())
    missing = capture_development_integrity(tmp_path / "absent", (table,))
    assert missing.directory_problem == "invalid_directory"
    assert not missing.passed
