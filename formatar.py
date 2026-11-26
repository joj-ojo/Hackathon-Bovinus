#!/usr/bin/env python
"""Gera versão legível em parágrafos a partir do .json da transcrição."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def ts(seconds: float) -> str:
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: python formatar.py transcricoes/arquivo.json [--com-tempo]", file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    com_tempo = "--com-tempo" in sys.argv
    data = json.loads(src.read_text(encoding="utf-8"))
    segs = data["segments"]

    blocos: list[list[dict]] = []
    atual: list[dict] = []
    limite = 900  # caracteres por parágrafo
    for i, seg in enumerate(segs):
        anterior = segs[i - 1] if i else None
        quebra = anterior is not None and (
            seg["start"] - anterior["end"] > 2.5
            or sum(len(s["text"]) + 1 for s in atual) > limite
        )
        if quebra and atual:
            blocos.append(atual)
            atual = []
        atual.append(seg)
    if atual:
        blocos.append(atual)

    linhas = [f"# {src.stem}", ""]
    for bloco in blocos:
        texto = " ".join(s["text"] for s in bloco)
        if com_tempo:
            linhas.append(f"**[{ts(bloco[0]['start'])}]** {texto}")
        else:
            linhas.append(texto)
        linhas.append("")

    dest = src.with_suffix(".md")
    dest.write_text("\n".join(linhas), encoding="utf-8")
    print(f"[ok] {len(blocos)} parágrafos -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
