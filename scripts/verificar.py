"""Verificação rápida do ambiente: banco, seed, CMV e pipeline de visão.

Rodar: python scripts/verificar.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import servico  # noqa: E402
from core.cmv import calcular_cmv  # noqa: E402
from core.db import init_db, sessao  # noqa: E402
from core.demo import gerar_todas  # noqa: E402
from core.seed import popular  # noqa: E402
from core.vision import analisar_bytes  # noqa: E402

FALHAS: list[str] = []


def checar(nome: str, condicao: bool, detalhe: str = "") -> None:
    marca = "OK  " if condicao else "FALHA"
    print(f"[{marca}] {nome}{f' — {detalhe}' if detalhe else ''}")
    if not condicao:
        FALHAS.append(nome)


print("1) Banco e seed")
init_db()
popular(force=False)
with sessao() as s:
    ind = servico.indicadores(s)
checar("comandas no dia", ind["comandas"] > 0, f"{ind['comandas']} comandas")
checar("CMV calculado", 10 < ind["cmv_pct"] < 45, f"CMV {ind['cmv_pct']:.1f}%")
checar("feedbacks presentes", ind["feedbacks"] > 0, f"{ind['feedbacks']} respostas")

print("\n2) Motor de CMV")
r = calcular_cmv(
    600,
    [
        {"categoria": "carne_premium", "percentual_area": 0.3},
        {"categoria": "acompanhamento", "percentual_area": 0.5},
        {"categoria": "salada_legume", "percentual_area": 0.2},
    ],
)
soma_peso = sum(i["peso_estimado_g"] for i in r.itens)
checar("peso distribuído bate com a balança", abs(soma_peso - 600) <= 1, f"{soma_peso} g")
checar("CMV entre 20% e 35%", 20 <= r.cmv_pct <= 35, f"{r.cmv_pct:.1f}%")
checar("receita = peso x 119", abs(r.receita - 71.4) < 0.01, f"R$ {r.receita:.2f}")

print("\n3) Pipeline de visão (offline)")
with sessao() as s:
    pratos = gerar_todas()
for prato in pratos:
    resultado = analisar_bytes(prato["caminho"].read_bytes(), prato["peso_g"], provider="heuristica")
    itens = len(resultado["itens"])
    checar(f"analisou '{prato['titulo']}'", itens >= 2, f"{itens} categorias, CMV {resultado['cmv']['cmv_pct']:.1f}%")

print("\n4) Fila e alertas")
with sessao() as s:
    alertas = servico.alertas_atuais(s)
checar("motor de alertas roda", isinstance(alertas, list), f"{len(alertas)} alertas")

print()
if FALHAS:
    print(f"Falharam {len(FALHAS)} verificações: {', '.join(FALHAS)}")
    sys.exit(1)
print("Tudo certo. Rode: streamlit run app/main.py")
