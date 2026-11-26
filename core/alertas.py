"""Regras de alerta. Funções puras: recebem contexto, devolvem alertas.

Cooldown fica a cargo de quem persiste (`core.servico`), para não alertar
a mesma coisa a cada rerun do Streamlit.
"""

from __future__ import annotations

from core.fluxo import (
    ALERTA_ESCADA_PESSOAS,
    META_CHURRASQUEIRA_MIN,
    META_LIMPEZA_MIN,
    prioridade_mesa,
    severidade_fila,
)


def alertas_de_fila(eventos: list[dict]) -> list[dict]:
    """eventos: [{zona, pessoas, espera_estimada_min}]."""
    saida = []
    for ev in eventos:
        sev = severidade_fila(ev["zona"], ev["pessoas"], ev["espera_estimada_min"])
        if not sev:
            continue
        if ev["zona"] == "entrada":
            msg = (
                f"{ev['pessoas']} pessoas na entrada — a fila chega na escada "
                f"(limite saudável: {ALERTA_ESCADA_PESSOAS}). Risco de desistência."
            )
        elif ev["zona"] == "churrasqueira":
            msg = (
                f"Espera estimada de {ev['espera_estimada_min']:.1f} min na churrasqueira "
                f"(meta: {META_CHURRASQUEIRA_MIN} min). Reforçar o atendimento."
            )
        else:
            msg = f"Fila de {ev['espera_estimada_min']:.1f} min no caixa."
        saida.append(
            {
                "tipo": f"FILA_{ev['zona'].upper()}",
                "severidade": sev,
                "entidade": ev["zona"],
                "mensagem": msg,
            }
        )
    return saida


def alertas_de_mesas(mesas: list[dict]) -> list[dict]:
    """mesas: [{id, minutos_livre, lugares, nivel}] já filtradas para 'suja'."""
    sujas = [m for m in mesas if m["minutos_livre"] >= META_LIMPEZA_MIN]
    if not sujas:
        return []
    sujas.sort(
        key=lambda m: prioridade_mesa(m["minutos_livre"], m["lugares"], m["nivel"]),
        reverse=True,
    )
    top = sujas[0]
    return [
        {
            "tipo": "MESA_SUJA",
            "severidade": "critica" if top["minutos_livre"] >= META_LIMPEZA_MIN * 2 else "media",
            "entidade": f"mesa {top['id']}",
            "mensagem": (
                f"{len(sujas)} mesa(s) aguardando higienização. Prioridade: mesa "
                f"{top['id']} ({top['lugares']} lugares, {top['nivel']}) livre há "
                f"{top['minutos_livre']:.0f} min."
            ),
        }
    ]


def alertas_de_cmv(cmv_pct: float, mix_premium_pct: float) -> list[dict]:
    if cmv_pct <= 32:
        return []
    return [
        {
            "tipo": "CMV_ALTO",
            "severidade": "alta" if cmv_pct > 36 else "media",
            "entidade": "dia",
            "mensagem": (
                f"CMV médio em {cmv_pct:.1f}% (acima da faixa de 28–32%). "
                f"Mix premium em {mix_premium_pct * 100:.1f}% do prato."
            ),
        }
    ]


def alertas_de_itens(itens: list[dict]) -> list[dict]:
    """itens: [{item, nota_media, avaliacoes}] — itens com pior aceitação."""
    piores = [i for i in itens if i["avaliacoes"] >= 3 and i["nota_media"] <= 2.4]
    return [
        {
            "tipo": "ITEM_BAIXA_ACEITACAO",
            "severidade": "media",
            "entidade": i["item"],
            "mensagem": (
                f"'{i['item']}' com nota média {i['nota_media']:.1f}/4 em "
                f"{i['avaliacoes']} avaliações. Avaliar receita ou retirar do buffet."
            ),
        }
        for i in piores[:3]
    ]


def gerar_alertas(contexto: dict) -> list[dict]:
    """Agrega todas as regras em uma lista única, ordenada por severidade."""
    alertas = []
    alertas += alertas_de_fila(contexto.get("fila", []))
    alertas += alertas_de_mesas(contexto.get("mesas_sujas", []))
    alertas += alertas_de_cmv(
        contexto.get("cmv_pct", 0.0), contexto.get("mix_premium_pct", 0.0)
    )
    alertas += alertas_de_itens(contexto.get("itens", []))
    ordem = {"critica": 0, "alta": 1, "media": 2, "baixa": 3}
    return sorted(alertas, key=lambda a: ordem.get(a["severidade"], 9))
