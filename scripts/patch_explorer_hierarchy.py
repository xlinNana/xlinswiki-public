#!/usr/bin/env python3
"""Keep Explorer grouped by source file paths when canonical slugs are flat."""

from __future__ import annotations

import argparse
from pathlib import Path

OLD = 'add(e){this.insert(e.slug.split("/"),e)}'
NEW = 'add(e){let D=(e.filePath||e.slug).replace(/\\.md$/,"");this.insert(D.split("/"),e)}'


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if NEW in text:
        return False
    if OLD not in text:
        raise RuntimeError(f"Explorer implementation pattern not found in {path}")
    path.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[
            Path("node_modules/@quartz-community/explorer/dist/index.js"),
            Path("node_modules/@quartz-community/explorer/dist/components/index.js"),
        ],
    )
    changed = 0
    for path in parser.parse_args().paths:
        changed += patch_file(path)
    print(f"Explorer hierarchy patch: updated {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
