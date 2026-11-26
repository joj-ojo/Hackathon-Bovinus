"""Smoke test das telas com o Streamlit AppTest: garante que nada quebra ao abrir."""

from __future__ import annotations

import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
PAGINAS = [
    "app/main.py",
    "app/pages/1_Balanca.py",
    "app/pages/2_Feedback.py",
    "app/pages/3_Painel.py",
    "app/pages/4_Mesas.py",
    "app/pages/5_Comandas.py",
]


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_abre_sem_excecao(pagina: str) -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(RAIZ / pagina), default_timeout=120)
    at.run()
    assert not at.exception, f"{pagina} levantou exceção: {at.exception}"
