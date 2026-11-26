"""Gera as imagens sintéticas dos pratos de demonstração."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.demo import gerar_todas  # noqa: E402

if __name__ == "__main__":
    for prato in gerar_todas(forcar=True):
        print(f"{prato['titulo']:<28} {prato['caminho']}  CMV {prato['cmv']['cmv_pct']:.1f}%")
