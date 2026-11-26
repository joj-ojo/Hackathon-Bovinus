"""Testes do motor de CMV — o núcleo que não pode errar."""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.cmv import calcular_cmv, distribuir_peso, normalizar_percentuais  # noqa: E402


def test_normalizar_soma_um():
    itens = normalizar_percentuais(
        [
            {"categoria": "carne_premium", "percentual_area": 2},
            {"categoria": "acompanhamento", "percentual_area": 2},
        ]
    )
    assert abs(sum(i["percentual_area"] for i in itens) - 1.0) < 1e-9


def test_normalizar_ignora_negativos():
    itens = normalizar_percentuais(
        [{"categoria": "salada_legume", "percentual_area": -0.5},
         {"categoria": "acompanhamento", "percentual_area": 1.0}]
    )
    assert itens == [{"categoria": "acompanhamento", "percentual_area": 1.0}]


def test_peso_distribuido_bate_com_balanca():
    itens = [
        {"categoria": "carne_premium", "percentual_area": 0.25},
        {"categoria": "acompanhamento", "percentual_area": 0.45},
        {"categoria": "salada_legume", "percentual_area": 0.30},
    ]
    detalhados = distribuir_peso(613, itens)
    assert abs(sum(i["peso_estimado_g"] for i in detalhados) - 613) <= 1


def test_densidade_muda_o_peso():
    """Mesma área, densidades diferentes: carne pesa mais que salada."""
    itens = [
        {"categoria": "carne_premium", "percentual_area": 0.5},
        {"categoria": "salada_legume", "percentual_area": 0.5},
    ]
    detalhados = {i["categoria"]: i["peso_estimado_g"] for i in distribuir_peso(600, itens)}
    assert detalhados["carne_premium"] > detalhados["salada_legume"]


def test_cmv_e_receita():
    resultado = calcular_cmv(
        500,
        [
            {"categoria": "carne_premium", "percentual_area": 0.5},
            {"categoria": "acompanhamento", "percentual_area": 0.5},
        ],
        preco_kg=119.0,
    )
    assert abs(resultado.receita - 59.5) < 1e-6
    assert resultado.cmv_pct > 0
    assert abs(resultado.margem_bruta - (resultado.receita - resultado.custo_total)) < 0.02


def test_premium_custa_mais_que_carboidrato():
    premium = calcular_cmv(600, [{"categoria": "carne_premium", "percentual_area": 1.0}])
    barato = calcular_cmv(600, [{"categoria": "acompanhamento", "percentual_area": 1.0}])
    assert premium.cmv_pct > barato.cmv_pct


def test_cmv_sem_itens_nao_quebra():
    resultado = calcular_cmv(600, [])
    assert resultado.itens == []
    assert resultado.custo_total == 0
    assert resultado.cmv_pct == 0


def test_peso_zero_nao_quebra():
    resultado = calcular_cmv(0, [{"categoria": "carne_premium", "percentual_area": 1.0}])
    assert resultado.receita == 0
    assert resultado.cmv_pct == 0
