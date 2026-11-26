"""Testes do contrato HTTP: é o que a integração com o SaaS vai consumir."""

from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


@pytest.fixture(scope="module")
def cliente():
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c


def test_health(cliente) -> None:
    resposta = cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_analisa_prato_e_persiste(cliente) -> None:
    from core.demo import gerar_todas

    foto = gerar_todas()[0]["caminho"]
    with foto.open("rb") as arquivo:
        resposta = cliente.post(
            "/api/v1/pratos/analisar",
            files={"foto": (foto.name, arquivo, "image/jpeg")},
            data={"comanda": "9001", "peso_g": "600", "persistir": "true"},
        )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["peso_total_g"] == 600
    assert corpo["cmv"]["cmv_pct"] > 0
    assert corpo["itens"]

    comanda = cliente.get("/api/v1/comandas/9001")
    assert comanda.status_code == 200
    assert len(comanda.json()["pratos"]) == 1


def test_feedback_vinculado_a_comanda(cliente) -> None:
    resposta = cliente.post(
        "/api/v1/feedback",
        json={"comanda": "9002", "nota_geral": 2, "item": "lasanha", "nota_item": 1, "resto": "muito"},
    )
    assert resposta.status_code == 201
    comanda = cliente.get("/api/v1/comandas/9002").json()
    assert comanda["feedbacks"][0]["nota_item"] == 1


def test_webhook_comanda_aberta_e_bebida(cliente) -> None:
    assert cliente.post(
        "/webhooks/comanda", json={"evento": "comanda.aberta", "comanda": "9003"}
    ).status_code == 202

    resposta = cliente.post(
        "/webhooks/comanda",
        json={
            "evento": "item.lancado",
            "comanda": "9003",
            "payload": {"tipo": "bebida", "valor": 12.5},
        },
    )
    assert resposta.status_code == 202

    comanda = cliente.get("/api/v1/comandas/9003").json()
    assert comanda["bebidas"] == pytest.approx(12.5, rel=1e-3)


def test_webhook_evento_invalido(cliente) -> None:
    resposta = cliente.post(
        "/webhooks/comanda", json={"evento": "comanda.inexistente", "comanda": "9004"}
    )
    assert resposta.status_code == 422


def test_indicadores_e_alertas(cliente) -> None:
    indicadores = cliente.get("/api/v1/indicadores").json()
    assert indicadores["comandas"] > 0
    assert 0 < indicadores["cmv_pct"] < 100

    alertas = cliente.get("/api/v1/alertas")
    assert alertas.status_code == 200
    assert isinstance(alertas.json(), list)
