#!/usr/bin/env python3
"""Sync XLinsWiki content assets to Tencent COS and rewrite built HTML URLs.

Required environment variables:
  COS_SECRET_ID, COS_SECRET_KEY
Optional:
  COS_SESSION_TOKEN, COS_REGION (default ap-guangzhou), COS_BUCKET

The script preserves the content-relative path under the xlinswiki/ prefix.
It never edits Markdown source files.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
PUBLIC = ROOT / "public"
PREFIX = os.environ.get("COS_PREFIX", "xlinswiki").strip("/")
REGION = os.environ.get("COS_REGION", "ap-guangzhou")
BUCKET = os.environ.get("COS_BUCKET", "xlinswiki-1329382380")
DOMAIN = os.environ.get(
    "COS_DOMAIN", f"https://{BUCKET}.cos.{REGION}.myqcloud.com"
).rstrip("/")

ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".bmp",
    ".mp4", ".webm", ".mov", ".mkv", ".mp3", ".wav", ".ogg", ".flac",
    ".pdf", ".woff", ".woff2", ".ttf", ".otf",
}
ATTR_RE = re.compile(r"(?P<prefix>\b(?:src|href)\s*=\s*[\"'])(?P<url>[^\"']+)(?P<suffix>[\"'])", re.I)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.I)
SRC_RE = re.compile(r"\bsrc\s*=\s*[\"'](?P<url>[^\"']+)[\"']", re.I)
EXPLORER_LIST_RE = re.compile(
    r'(<ul class="explorer-ul overflow" id="list-\d+">).*?(<li class="overflow-end"></li></ul>)',
    re.I | re.S,
)


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def sync_assets(dry_run: bool) -> None:
    coscli = os.environ.get("COSCLI", str(Path.home() / "coscli"))
    if not Path(coscli).is_file() and shutil.which(coscli) is None:
        die(f"coscli not found: {coscli}")
    assets = sorted(p for p in CONTENT.rglob("*") if p.is_file() and p.suffix.lower() in ASSET_EXTENSIONS)
    print(f"found {len(assets)} assets under {CONTENT}")
    if not assets:
        # coscli rejects an empty staging directory. A published vault may
        # legitimately contain only Markdown, so there is nothing to upload.
        return
    if dry_run:
        for asset in assets:
            print(f"DRY-RUN upload {asset.relative_to(CONTENT).as_posix()} -> {PREFIX}/{asset.relative_to(CONTENT).as_posix()}")
        return
    with tempfile.TemporaryDirectory(prefix="xlinswiki-cos-", dir=ROOT) as staging:
        stage = Path(staging) / PREFIX
        for asset in assets:
            target = stage / asset.relative_to(CONTENT)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(asset, target)
        destination = f"cos://{BUCKET}/{PREFIX}/"
        cmd = [coscli, "sync", "-r", str(stage) + "/", destination,
               "--update", "--skip-dir", "--force", "--routines", "2",
               "--thread-num", "2", "--meta", "Cache-Control:public, max-age=31536000"]
        print("running:", " ".join(cmd[:5]), "...")
        subprocess.run(cmd, cwd=ROOT, check=True)


def resolve_content_rel(public_rel: Path) -> Path | None:
    """Map Quartz's emitted (often lower-cased) asset path back to content."""
    current = CONTENT
    resolved_parts: list[str] = []
    for part in public_rel.parts:
        exact = current / part
        if exact.exists():
            chosen = exact
        else:
            matches = [candidate for candidate in current.iterdir() if candidate.name.casefold() == part.casefold()]
            if len(matches) != 1:
                return None
            chosen = matches[0]
        resolved_parts.append(chosen.name)
        current = chosen
    return Path(*resolved_parts)


def source_for_public_rel(public_rel: Path) -> tuple[Path, Path] | None:
    """Return (source file, original content-relative path) for a public asset."""
    rel = resolve_content_rel(public_rel)
    if rel is None:
        return None
    source = CONTENT / rel
    return (source, rel) if source.is_file() else None


def public_url(rel: str) -> str:
    return DOMAIN + "/" + "/".join(quote(part, safe="") for part in f"{PREFIX}/{rel}".split("/"))


def is_content_image(html: Path, raw_url: str) -> bool:
    parsed = urlsplit(raw_url)
    if parsed.scheme or parsed.netloc:
        return raw_url.startswith(f"{DOMAIN}/{PREFIX}/")
    if raw_url.startswith(("#", "data:", "/static/")):
        return False
    candidate = (html.parent / unquote(parsed.path)).resolve()
    rel = resolve_content_rel(candidate.relative_to(PUBLIC))
    if rel is None:
        return False
    return rel.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".bmp"} and (CONTENT / rel).is_file()


def add_lazy_loading(html: Path, text: str) -> tuple[str, int]:
    count = 0

    def enhance(match: re.Match[str]) -> str:
        nonlocal count
        tag = match.group(0)
        src_match = SRC_RE.search(tag)
        if not src_match or not is_content_image(html, src_match.group("url")):
            return tag
        additions = []
        if not re.search(r"\bloading\s*=", tag, re.I):
            additions.append('loading="lazy"')
        if not re.search(r"\bdecoding\s*=", tag, re.I):
            additions.append('decoding="async"')
        if not additions:
            return tag
        count += 1
        closing = "/>" if tag.endswith("/>") else ">"
        return tag[: -len(closing)].rstrip() + " " + " ".join(additions) + closing

    return IMG_TAG_RE.sub(enhance, text), count


def explorer_fallback() -> str:
    """Render a static explorer tree for first paint before client JS runs."""
    index_path = PUBLIC / "static" / "contentIndex.json"
    if not index_path.is_file():
        return ""
    data = json.loads(index_path.read_text(encoding="utf-8"))
    root: dict[str, object] = {"folders": {}, "files": []}
    for slug, details in data.items():
        if slug in {"index", "tags"} or slug.startswith("tags/"):
            continue
        parts = slug.split("/")
        node = root
        for part in parts[:-1]:
            folders = node["folders"]
            assert isinstance(folders, dict)
            node = folders.setdefault(part, {"folders": {}, "files": []})
        files = node["files"]
        assert isinstance(files, list)
        files.append((parts[-1], details.get("title") or parts[-1], slug))

    def render(node: dict[str, object], prefix: str = "") -> str:
        chunks: list[str] = []
        folders = node["folders"]
        files = node["files"]
        assert isinstance(folders, dict) and isinstance(files, list)
        for name in sorted(folders, key=str.casefold):
            child = folders[name]
            path = f"{prefix}/{name}" if prefix else name
            chunks.append(
                '<li class="explorer-fallback-folder">'
                f'<div class="folder-container nav-folder-title tree-item-self" data-folderpath="{escape(path)}/index">'
                '<span class="folder-icon nav-folder-collapse-indicator collapse-icon" aria-hidden="true">›</span>'
                f'<div><a class="folder-button" href="/{quote(path, safe="/")}/"><span class="folder-title">{escape(name)}</span></a></div>'
                '</div>'
                f'<div class="folder-outer"><ul class="content tree-item-children">{render(child, path)}</ul></div>'
                '</li>'
            )
        for _, title, slug in sorted(files, key=lambda item: str(item[1]).casefold()):
            chunks.append(
                f'<li><a href="/{quote(str(slug), safe="/")}" class="nav-file-title tree-item-self">{escape(str(title))}</a></li>'
            )
        return "".join(chunks)

    return render(root)


def rewrite_html() -> int:
    if not PUBLIC.exists():
        die("public/ does not exist; run the Quartz build before rewriting URLs")
    changed = 0
    lazy_images = 0
    fallback = explorer_fallback()
    explorer_pages = 0
    for html in PUBLIC.rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        def replace(match: re.Match[str]) -> str:
            raw = match.group("url")
            parsed = urlsplit(raw)
            if parsed.scheme or parsed.netloc or raw.startswith(("#", "data:", "/static/")):
                return match.group(0)
            rel_url = unquote(parsed.path)
            candidate = (html.parent / rel_url).resolve()
            try:
                public_rel = candidate.relative_to(PUBLIC)
            except ValueError:
                return match.group(0)
            resolved = source_for_public_rel(public_rel)
            if resolved is None:
                return match.group(0)
            source, rel = resolved
            if rel.suffix.lower() not in ASSET_EXTENSIONS:
                return match.group(0)
            return match.group("prefix") + public_url(rel.as_posix()) + match.group("suffix")
        updated = ATTR_RE.sub(replace, text)
        updated, added = add_lazy_loading(html, updated)
        lazy_images += added
        if fallback and EXPLORER_LIST_RE.search(updated):
            updated, replaced = EXPLORER_LIST_RE.subn(
                lambda match: match.group(1) + fallback + match.group(2), updated, count=1
            )
            explorer_pages += replaced
        if updated != text:
            html.write_text(updated, encoding="utf-8")
            changed += 1
    print(
        f"rewrote {changed} HTML files; added lazy loading to {lazy_images} content images; "
        f"embedded explorer fallback in {explorer_pages} pages"
    )
    return changed


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    rewrite_only = "--rewrite-only" in sys.argv
    if not rewrite_only:
        sync_assets(dry_run)
    if not dry_run or rewrite_only:
        rewrite_html()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
