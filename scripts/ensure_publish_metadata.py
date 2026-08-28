#!/usr/bin/env python3
"""Assign stable publication dates and short global-sequence slugs to notes."""

from __future__ import annotations

import argparse
import re
from datetime import date, datetime
from pathlib import Path
from typing import Callable

DATE_RE = re.compile(r"(?m)^date:\s*[\"']?(\d{4}-\d{2}-\d{2})[\"']?\s*$")
LEGACY_DATA_RE = re.compile(r"(?m)^data:\s*[\"']?(\d{4}-\d{2}-\d{2})[\"']?\s*$")
SLUG_RE = re.compile(r"(?m)^slug:\s*[\"']?(\d{6})[\"']?\s*$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


def filesystem_creation_date(path: Path) -> date:
    # Syncthing normally preserves the source file's modification timestamp but
    # creates a new inode on the server, so server-side birth time reflects the
    # sync event rather than the note's original date. The assigned `data` value
    # is written once and remains stable through later edits.
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def _read_metadata(text: str) -> tuple[str | None, str | None]:
    match = FRONTMATTER_RE.match(text)
    frontmatter = match.group(1) if match else ""
    date_match = DATE_RE.search(frontmatter) or LEGACY_DATA_RE.search(frontmatter)
    slug_match = SLUG_RE.search(frontmatter)
    return (
        date_match.group(1) if date_match else None,
        slug_match.group(1) if slug_match else None,
    )


def _migrate_legacy_data(text: str) -> str:
    match = FRONTMATTER_RE.match(text)
    if not match or DATE_RE.search(match.group(1)) or not LEGACY_DATA_RE.search(match.group(1)):
        return text
    migrated = LEGACY_DATA_RE.sub(lambda item: f"date: {item.group(1)}", match.group(1), count=1)
    return f"---\n{migrated}\n---\n" + text[match.end() :]


def _has_current_metadata(text: str) -> bool:
    match = FRONTMATTER_RE.match(text)
    return bool(match and DATE_RE.search(match.group(1)) and SLUG_RE.search(match.group(1)))


def _insert_metadata(text: str, date_value: str, slug: str) -> str:
    metadata = f"date: {date_value}\nslug: '{slug}'"
    match = FRONTMATTER_RE.match(text)
    if match:
        existing = match.group(1)
        replacement = f"---\n{metadata}\n{existing}\n---\n"
        return replacement + text[match.end() :]
    return f"---\n{metadata}\n---\n{text}"


def ensure_metadata(
    root: Path,
    creation_date: Callable[[Path], date] = filesystem_creation_date,
    now: datetime | None = None,
) -> list[Path]:
    del now  # Reserved for deterministic callers and future validation.
    root = root.resolve()
    notes = sorted(path for path in root.rglob("*.md") if path.name.lower() != "index.md")

    seen: dict[str, Path] = {}
    maximum_sequence = 0
    pending: list[tuple[Path, str, date]] = []

    for path in notes:
        original_text = path.read_text(encoding="utf-8")
        text = _migrate_legacy_data(original_text)
        date_value, slug = _read_metadata(text)
        if slug:
            if slug in seen:
                raise ValueError(f"duplicate slug {slug}: {seen[slug]} and {path}")
            seen[slug] = path
            maximum_sequence = max(maximum_sequence, int(slug[-2:]))
        if text != original_text or not date_value or not slug:
            pending.append((path, text, creation_date(path)))

    changed: list[Path] = []
    for path, text, created in sorted(pending, key=lambda item: (item[2], str(item[0]))):
        date_value, slug = _read_metadata(text)
        if slug is None:
            maximum_sequence += 1
            if maximum_sequence > 99:
                raise ValueError("publication sequence exceeds two digits")
            slug = f"{created:%m%d}{maximum_sequence:02d}"
            if slug in seen:
                raise ValueError(f"duplicate slug {slug}: {seen[slug]} and {path}")
            seen[slug] = path
        if date_value is None:
            date_value = created.isoformat()
        if _has_current_metadata(text):
            updated = text
        else:
            updated = _insert_metadata(text, date_value, slug)
        path.write_text(updated, encoding="utf-8")
        changed.append(path)

    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    changed = ensure_metadata(args.root)
    print(f"publication metadata: updated {len(changed)} note(s)")
    for path in changed:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
