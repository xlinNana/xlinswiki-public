#!/usr/bin/env python3
"""Create the Quartz input tree for GitHub Pages.

Only Markdown is copied into the repository. Relative media references are
converted to public Tencent COS URLs before Quartz builds the site.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "content-github"
DEST = ROOT / "content"
DOMAIN = "https://xlinswiki-1329382380.cos.ap-guangzhou.myqcloud.com"
PREFIX = "xlinswiki"
MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".bmp",
    ".mp4", ".webm", ".mov", ".mkv", ".mp3", ".wav", ".ogg", ".flac",
    ".pdf", ".woff", ".woff2", ".ttf", ".otf",
}
LINK_RE = re.compile(r"(?P<open>!?\[[^\]]*\]\()(?P<url>[^)\s]+)(?P<close>\))")


def cos_url(relative: str) -> str:
    return DOMAIN + "/" + "/".join(
        quote(part, safe="") for part in f"{PREFIX}/{relative}".split("/")
    )


if DEST.exists() or DEST.is_symlink():
    if DEST.is_symlink() or DEST.is_file():
        DEST.unlink()
    else:
        shutil.rmtree(DEST)
DEST.mkdir(parents=True)

rewritten = 0
for source_file in SOURCE.rglob("*.md"):
    relative_md = source_file.relative_to(SOURCE)
    destination = DEST / relative_md
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = source_file.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        global rewritten
        raw = match.group("url")
        parsed = urlsplit(raw)
        if parsed.scheme or parsed.netloc or raw.startswith(("#", "/", "data:")):
            return match.group(0)
        media_path = Path(parsed.path)
        if media_path.suffix.lower() not in MEDIA_EXTENSIONS:
            return match.group(0)
        # Obsidian occasionally stores a vault-relative link with the
        # published-folder name included. COS is synced from that folder, so
        # remove the staging prefix and preserve the remaining vault-relative
        # path. Decode once first so spaces are not double-encoded in COS URLs.
        relative = unquote((relative_md.parent / media_path).as_posix())
        relative = relative.replace("03-Published/", "")
        relative = relative.removeprefix("03-Published/")
        # CI intentionally has no binary attachments. The COS sync convention
        # stores a same-folder Markdown attachment in an adjacent `附件`
        # directory, so this logical path is sufficient without local files.
        if len(media_path.parts) == 1 and relative_md.parent != Path("."):
            relative = (relative_md.parent / "附件" / unquote(media_path.name)).as_posix()
        relative = relative.replace("03-Published/", "")
        relative = relative.removeprefix("03-Published/")
        rewritten += 1
        url = cos_url(relative)
        if parsed.query:
            url += "?" + parsed.query
        if parsed.fragment:
            url += "#" + parsed.fragment
        return match.group("open") + url + match.group("close")

    destination.write_text(LINK_RE.sub(replace, text), encoding="utf-8")

print(f"prepared {len(list(DEST.rglob('*.md')))} Markdown files; rewrote {rewritten} COS media links")
