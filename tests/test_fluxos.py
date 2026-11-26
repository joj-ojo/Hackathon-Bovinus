"""Testes de interação: as ações principais da demo precisam funcionar."""

from __future__ import annotations

import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _app(relativo: str):
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(RAIZ / relativo), default_timeout=120)


def _por_label(at, label: str):
    for botao in at.button:
        if botao.label == label:
            return botao
    return None


def test_balanca_analisa_prato_de_demonstracao() -> None:
    at = _app("app/pages/1_Balanca.py")
    at.run()
    at.radio[0].set_value("Prato de demonstração")
    at.run()

    botao = _por_label(at, "Analisar prato")
    assert botao is not None
    botao.click().run()

    assert not at.exception, at.exception
    analise = at.session_state["b_analise"]
    assert analise is not None
    assert analise["cmv"]["cmv_pct"] > 0
    assert len(analise["itens"]) >= 2


def test_feedback_registra_nota() -> None:
    at = _app("app/pages/2_Feedback.py")
    at.run()

    botao = next((b for b in at.button if b.key == "nota_4"), None)
    assert botao is not None
    botao.click().run()

    assert not at.exception, at.exception
    assert at.session_state["fb_nota"] == 4


def test_mesas_higieniza_mesa_prioritaria() -> None:
    at = _app("app/pages/4_Mesas.py")
    at.run()

    botao = _por_label(at, "Higienizada")
    if botao is None:
        pytest.skip("Nenhuma mesa suja no seed atual.")
    botao.click().run()

    assert not at.exception, at.exception


def test_painel_renderiza_graficos() -> None:
    at = _app("app/pages/3_Painel.py")
    at.run()
    assert not at.exception, at.exception
    assert len(at.selectbox) >= 1
