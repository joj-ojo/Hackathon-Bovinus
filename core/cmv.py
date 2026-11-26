"""Motor de CMV: converte (peso total + composição por área) em reais.

A conta central é a normalização por densidade superficial:

    peso_i = peso_total * (a_i * d_i) / soma(a_j * d_j)

porque área não é peso: 100 cm² de salada pesam muito menos que 100 cm² de picanha.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.custos import CATEGORIAS_PADRAO


@dataclass
class ItemComposicao:
    categoria: str
    rotulo: str = ""
    percentual_area: float = 0.0
    confianca: float = 1.0


@dataclass
class ResultadoCMV:
    itens: list[dict] = field(default_factory=list)
    custo_total: float = 0.0
    receita: float = 0.0
    cmv_pct: float = 0.0
    margem_bruta: float = 0.0
    custo_por_kg: float = 0.0
    mix_premium_pct: float = 0.0

    def como_dict(self) -> dict:
        return {
            "itens": self.itens,
            "cmv": {
                "custo_total": round(self.custo_total, 2),
                "receita": round(self.receita, 2),
                "cmv_pct": round(self.cmv_pct, 2),
                "margem_bruta": round(self.margem_bruta, 2),
                "custo_por_kg": round(self.custo_por_kg, 2),
            },
            "mix_premium_pct": round(self.mix_premium_pct, 4),
        }


def normalizar_percentuais(itens: list[dict]) -> list[dict]:
    """Garante que os percentuais de área somem 1 (ignora valores negativos)."""
    limpos = [{**i, "percentual_area": max(0.0, float(i.get("percentual_area", 0.0)))} for i in itens]
    limpos = [i for i in limpos if i["percentual_area"] > 0]
    total = sum(i["percentual_area"] for i in limpos)
    if total <= 0:
        return []
    for i in limpos:
        i["percentual_area"] = i["percentual_area"] / total
    return limpos


def distribuir_peso(
    peso_total_g: float,
    itens: list[dict],
    categorias: dict[str, dict] | None = None,
) -> list[dict]:
    """Reparte o peso real da balança entre as categorias, corrigindo por densidade."""
    categorias = categorias or CATEGORIAS_PADRAO
    itens = normalizar_percentuais(itens)
    if not itens or peso_total_g <= 0:
        return []

    massas_relativas = [
        i["percentual_area"] * categorias.get(i["categoria"], {}).get("densidade", 1.0)
        for i in itens
    ]
    soma = sum(massas_relativas) or 1.0

    resultado = []
    for item, massa in zip(itens, massas_relativas, strict=True):
        cat = categorias.get(item["categoria"], {})
        custo_kg = float(cat.get("custo_kg", 0.0))
        peso_g = peso_total_g * (massa / soma)
        resultado.append(
            {
                "categoria": item["categoria"],
                "rotulo": item.get("rotulo") or cat.get("rotulo", item["categoria"]),
                "percentual_area": round(item["percentual_area"], 4),
                "peso_estimado_g": round(peso_g),
                "custo_kg": custo_kg,
                "custo": round(peso_g / 1000 * custo_kg, 2),
                "confianca": round(float(item.get("confianca", 1.0)), 3),
            }
        )

    # Ajuste fino: o arredondamento não pode fazer a soma divergir do peso real.
    diferenca = round(peso_total_g) - sum(i["peso_estimado_g"] for i in resultado)
    if resultado and diferenca:
        maior = max(resultado, key=lambda i: i["peso_estimado_g"])
        maior["peso_estimado_g"] += diferenca
        maior["custo"] = round(maior["peso_estimado_g"] / 1000 * maior["custo_kg"], 2)

    return resultado


def calcular_cmv(
    peso_total_g: float,
    itens: list[dict],
    preco_kg: float = 119.0,
    categorias: dict[str, dict] | None = None,
) -> ResultadoCMV:
    """Calcula composição, custo, receita, CMV% e margem de um prato."""
    detalhados = distribuir_peso(peso_total_g, itens, categorias)

    custo_total = sum(i["custo"] for i in detalhados)
    receita = peso_total_g / 1000 * preco_kg
    custo_por_kg = (custo_total / (peso_total_g / 1000)) if peso_total_g else 0.0
    mix_premium = sum(
        i["percentual_area"] for i in detalhados if i["categoria"] == "carne_premium"
    )

    return ResultadoCMV(
        itens=detalhados,
        custo_total=custo_total,
        receita=receita,
        cmv_pct=(custo_total / receita * 100) if receita else 0.0,
        margem_bruta=receita - custo_total,
        custo_por_kg=custo_por_kg,
        mix_premium_pct=mix_premium,
    )


def margem_comanda(valor_prato: float, custo_prato: float, bebidas: float) -> dict:
    """Margem da comanda completa (prato + bebida). Bebida entra com custo estimado de 30%."""
    custo_bebida = bebidas * 0.30
    receita = valor_prato + bebidas
    custo = custo_prato + custo_bebida
    return {
        "receita": round(receita, 2),
        "custo": round(custo, 2),
        "margem": round(receita - custo, 2),
        "cmv_pct": round(custo / receita * 100, 2) if receita else 0.0,
    }
