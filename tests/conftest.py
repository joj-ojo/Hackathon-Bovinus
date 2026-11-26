"""Configuração dos testes: banco isolado para não sujar o demo.

Precisa rodar antes de qualquer import de `core`, porque a configuração é lida
uma única vez na importação.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_BANCO_TESTE = Path(tempfile.gettempdir()) / "bovinos_test.db"
if _BANCO_TESTE.exists():
    _BANCO_TESTE.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{_BANCO_TESTE.as_posix()}"
os.environ["SEED_COMANDAS_POR_DIA"] = "40"
os.environ["VISION_PROVIDER"] = "heuristica"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)
