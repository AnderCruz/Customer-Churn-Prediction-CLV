"""Bounded local acquisition and integrity evidence for the approved public sources."""

import argparse
import hashlib
import json
import shutil
import stat
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from time import monotonic
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, build_opener
from zipfile import BadZipFile, ZipFile, ZipInfo

_MIB = 1024 * 1024


class SourceError(ValueError):
    """A public-source input failed validation."""


@dataclass(frozen=True)
class Source:
    publisher: str
    page: str
    url: str
    licence: str
    classification: str
    release: str
    attribution: str
    limit: int


SOURCES = {
    "misata_saas": Source(
        "Misata Studio",
        "https://www.misata.studio/datasets/saas-subscription-analytics",
        "https://www.misata.studio/datasets/saas-subscription-analytics.zip",
        "CC0-1.0",
        "third-party synthetic",
        "publisher seed 20260722; no release number",
        "Attribution optional under CC0.",
        4 * _MIB,
    ),
    "uci_online_retail_ii": Source(
        "UCI Machine Learning Repository",
        "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
        "https://archive.ics.uci.edu/static/public/502/online%2Bretail%2Bii.zip",
        "CC-BY-4.0",
        "historical retail transactions",
        "dataset 502; no file version specified",
        "Chen, D. (2012). Online Retail II. UCI Machine Learning Repository. "
        "https://doi.org/10.24432/C5CG6D",
        60 * _MIB,
    ),
}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceError("The official download returned an unexpected redirect.")


def file_evidence(path: Path) -> dict:
    with path.open("rb") as stream:
        return {
            "filename": path.name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
        }


def safe_members(archive: ZipFile, *, expanded_limit: int, member_limit: int = 32) -> list[ZipInfo]:
    members = archive.infolist()
    if not members or len(members) > member_limit:
        raise SourceError("Unexpected number of archive members.")
    names = set()
    for member in members:
        name = member.filename
        path = PurePosixPath(name)
        mode = stat.S_IFMT(member.external_attr >> 16)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or ":" in name
            or name == "."
            or name != path.as_posix()
            or name.casefold() in names
            or mode not in (0, stat.S_IFREG)
            or member.flag_bits & 1
        ):
            raise SourceError("Unsafe archive member.")
        names.add(name.casefold())
    if sum(member.file_size for member in members) > expanded_limit:
        raise SourceError("Archive exceeds its expanded size budget.")
    return members


def _download(source: Source, target: Path) -> None:
    deadline = monotonic() + 120
    try:
        with (
            build_opener(_NoRedirect()).open(source.url, timeout=30) as response,
            target.open("xb") as output,
        ):
            total = 0
            while chunk := response.read1(_MIB):
                if monotonic() > deadline:
                    raise SourceError("Official download exceeded its time budget.")
                total += len(chunk)
                if total > source.limit:
                    raise SourceError("Official download exceeds its size budget.")
                output.write(chunk)
    except (URLError, OSError) as exc:
        raise SourceError("Official download failed.") from exc


def acquire(source_id: str, root: Path) -> Path:
    """Acquire an official archive, retain its bytes, and record member evidence."""
    source = SOURCES[source_id]
    destination = root / source_id
    root.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise SourceError("Source directory already exists; preserve the earlier acquisition.")
    with TemporaryDirectory(prefix=".acquire-", dir=root) as staging:
        path = Path(staging)
        archive_path = path / source.url.rsplit("/", 1)[1].replace("%2B", "+")
        _download(source, archive_path)
        try:
            with ZipFile(archive_path) as archive:
                members = safe_members(archive, expanded_limit=source.limit)
                names = {member.filename for member in members}
                if source_id == "uci_online_retail_ii" and names != {"online_retail_II.xlsx"}:
                    raise SourceError("Unexpected UCI archive inventory.")
                if source_id == "misata_saas":
                    from .misata import REQUIRED_FILES

                    if not REQUIRED_FILES <= names:
                        raise SourceError("Missing required Misata archive tables.")
                inventory = []
                for member in members:
                    target = path / member.filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as reader, target.open("xb") as writer:
                        shutil.copyfileobj(reader, writer, _MIB)
                    inventory.append(file_evidence(target) | {"filename": member.filename})
        except (BadZipFile, NotImplementedError, RuntimeError) as exc:
            raise SourceError("Malformed or unsupported source archive.") from exc
        evidence = {
            "source": source_id,
            **asdict(source),
            "acquired_at": datetime.now(UTC).isoformat(),
            "archive": file_evidence(archive_path),
            "members": inventory,
        }
        workbook = path / "online_retail_II.xlsx"
        if workbook.exists():
            from .retail import sheet_names

            evidence.update(format="xlsx", sheets=sheet_names(workbook))
        (path / "provenance.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        path.rename(destination)
    return destination


def verify_acquisition(directory: Path) -> dict:
    """Recompute evidence for the local archive and original files."""
    try:
        manifest = directory / "provenance.json"
        if manifest.stat().st_size > 65_536:
            raise ValueError
        evidence = json.loads(manifest.read_text(encoding="utf-8"))
        source = SOURCES[evidence["source"]]
        if any(evidence[key] != value for key, value in asdict(source).items()):
            raise ValueError
        items = (evidence["archive"], *evidence["members"])
        if len(items) > 33:
            raise ValueError
        for item in items:
            name = item["filename"]
            path = directory / name
            if (
                not path.resolve().is_relative_to(directory.resolve())
                or not path.is_file()
                or path.stat().st_size > source.limit
                or (file_evidence(path) | {"filename": name}) != item
            ):
                raise ValueError
        with ZipFile(directory / evidence["archive"]["filename"]) as archive:
            members = safe_members(archive, expanded_limit=source.limit)
            if {member.filename: member.file_size for member in members} != {
                item["filename"]: item["bytes"] for item in evidence["members"]
            } or len(members) != len(evidence["members"]):
                raise ValueError
    except (OSError, ValueError, TypeError, KeyError, BadZipFile):
        raise SourceError("Recorded source integrity does not match local files.") from None
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("acquire", "verify"))
    parser.add_argument("source", choices=SOURCES)
    parser.add_argument("--root", type=Path, default=Path("data/external"))
    args = parser.parse_args()
    directory = args.root / args.source
    if args.action == "acquire":
        print(acquire(args.source, args.root))
    else:
        verify_acquisition(directory)
        if args.source == "misata_saas":
            from .misata import load_misata

            evidence = load_misata(directory).quality
        else:
            from .retail import audit_retail

            evidence = audit_retail(directory / "online_retail_II.xlsx")
        print(json.dumps(evidence, indent=2, default=str))


if __name__ == "__main__":
    main()
