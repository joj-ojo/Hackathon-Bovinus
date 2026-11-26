"""Configuração central do projeto (variáveis de ambiente + caminhos)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RAIZ = Path(__file__).resolve().parents[1]
DATA_DIR = RAIZ / "data"
FOTOS_DIR = DATA_DIR / "fotos"
PRATOS_DIR = DATA_DIR / "pratos"

for _pasta in (DATA_DIR, FOTOS_DIR, PRATOS_DIR):
    _pasta.mkdir(parents=True, exist_ok=True)


class Settings:
    """Configuração única, lida uma vez. Nada aqui pode falhar se o .env estiver vazio."""

    def __init__(self) -> None:
        self.database_url: str = os.getenv("DATABASE_URL") or (
            f"sqlite:///{(DATA_DIR / 'bovinos.db').as_posix()}"
        )
        self.preco_kg: float = float(os.getenv("PRECO_KG", "119.0"))

        # auto -> tenta VLM, cai para heurística; heuristica -> nunca chama a nuvem
        self.vision_provider: str = os.getenv("VISION_PROVIDER", "auto").lower()

        self.gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv(
            "GOOGLE_API_KEY"
        )
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        self.seed_comandas_por_dia: int = int(os.getenv("SEED_COMANDAS_POR_DIA", "180"))

    @property
    def tem_vlm(self) -> bool:
        return bool(self.gemini_api_key or self.openai_api_key)


settings = Settings()
