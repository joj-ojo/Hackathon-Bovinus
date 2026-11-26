"""Testes de fila, prioridade de mesa e alertas."""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.alertas import gerar_alertas  # noqa: E402
from core.fluxo import (  # noqa: E402
    fila_maxima,
    prioridade_mesa,
    severidade_fila,
)


def test_little_4_minutos():
    """600 clientes em 70 min => 8,6/min. 34 pessoas => ~4 min de espera."""
    from core.fluxo import espera_estimada

    assert 3.9 < espera_estimada(34, 8.6) < 4.1


def test_fila_maxima_para_meta():
    """Para cumprir 2,5 min a 8,6 chegadas/min, a fila não passa de ~21 pessoas."""
    limiar = fila_maxima(8.6, 2.5)
    assert 20 <= limiar <= 22


def test_fila_zerada_nao_divide_por_zero():
    from core.fluxo import espera_estimada

    assert espera_estimada(10, 0) == 0.0


def test_escada_e_critica():
    assert severidade_fila("entrada", 14, 1.8) == "critica"


def test_churrasqueira_acima_da_meta():
    assert severidade_fila("churrasqueira", 20, 4.0) == "critica"


def test_mesa_grande_e_mais_prioritaria():
    pequena = prioridade_mesa(5, 2, "superior")
    grande = prioridade_mesa(5, 8, "principal")
    assert grande > pequena


def test_alertas_ordenados_por_severidade():
    contexto = {
        "fila": [
            {"zona": "entrada", "pessoas": 15, "espera_estimada_min": 2.0},
            {"zona": "caixa", "pessoas": 3, "espera_estimada_min": 3.5},
        ],
        "mesas_sujas": [
            {"id": 7, "minutos_livre": 8, "lugares": 8, "nivel": "principal"}
        ],
        "cmv_pct": 34.0,
        "mix_premium_pct": 0.28,
        "itens": [{"item": "lasanha", "nota_media": 2.05, "avaliacoes": 12}],
    }
    alertas = gerar_alertas(contexto)
    assert alertas[0]["severidade"] in ("critica", "alta")
    assert any(a["tipo"] == "MESA_SUJA" for a in alertas)
    assert any(a["tipo"] == "ITEM_BAIXA_ACEITACAO" for a in alertas)
