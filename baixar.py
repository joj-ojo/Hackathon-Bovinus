#!/usr/bin/env python
"""
Baixa o audio de um video/live do YouTube (ou qualquer site suportado) para .\\midia.

Uso:
  .venv\\Scripts\\python baixar.py "https://www.youtube.com/live/XXXX"
"""

from __future__ import annotations

import sys
from pathlib import Path

import yt_dlp

OUT = Path("midia")


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: python baixar.py <url>", file=sys.stderr)
        return 2
    url = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(OUT / "%(title).120B [%(id)s].%(ext)s"),
        "noprogress": False,
        "concurrent_fragment_downloads": 4,
        "retries": 10,
        "fragment_retries": 10,
        "live_from_start": True,
        "quiet": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
    print(f"\n[ok] arquivo: {path}")
    print(f"[proximo] .venv\\Scripts\\python transcrever.py \"{path}\" --lang pt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
