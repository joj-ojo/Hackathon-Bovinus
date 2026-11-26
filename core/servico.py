"""Serviços de leitura/escrita usados pelas telas e pela API.

Mantém as páginas do Streamlit finas: aqui ficam as consultas e as regras de
negócio que não são de visão computacional nem de CMV.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.alertas import gerar_alertas
from core.fluxo import prioridade_mesa
from core.models import (
    Alerta,
    Comanda,
    EventoFila,
    Feedback,
    Mesa,
    Pesagem,
    PesagemItem,
    ReposicaoCuba,
)


def hoje() -> date:
    return date.today()


def _intervalo(dia: date) -> tuple[datetime, datetime]:
    inicio = datetime.combine(dia, time.min)
    return inicio, inicio + timedelta(days=1)


def _p95(valores: list[float]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, int(round(0.95 * (len(ordenados) - 1))))
    return ordenados[indice]


# ---------------------------------------------------------------- indicadores


def indicadores(s, dia: date | None = None) -> dict:
    dia = dia or hoje()
    inicio, fim = _intervalo(dia)

    comandas = list(
        s.scalars(select(Comanda).where(Comanda.aberta_em >= inicio, Comanda.aberta_em < fim))
    )
    pesagens = list(
        s.scalars(select(Pesagem).where(Pesagem.criado_em >= inicio, Pesagem.criado_em < fim))
    )
    feedbacks = list(
        s.scalars(select(Feedback).where(Feedback.criado_em >= inicio, Feedback.criado_em < fim))
    )
    eventos = list(
        s.scalars(
            select(EventoFila).where(
                EventoFila.criado_em >= inicio,
                EventoFila.criado_em < fim,
                EventoFila.zona == "churrasqueira",
            )
        )
    )

    receita_prato = sum(p.receita_prato for p in pesagens)
    custo = sum(p.custo_estimado for p in pesagens)
    bebidas = sum(c.bebidas_valor for c in comandas)
    custo_bebida = bebidas * 0.30
    receita_total = receita_prato + bebidas

    mesas_sujas = list(s.scalars(select(Mesa).where(Mesa.status == "suja")))
    agora = datetime.now()
    minutos_sujas = [
        (agora - m.livre_desde).total_seconds() / 60 for m in mesas_sujas if m.livre_desde
    ]

    return {
        "dia": dia,
        "comandas": len(comandas),
        "comandas_abertas": sum(1 for c in comandas if not c.fechada_em),
        "pesagens": len(pesagens),
        "receita_prato": round(receita_prato, 2),
        "receita_total": round(receita_total, 2),
        "custo_prato": round(custo, 2),
        "cmv_pct": round(custo / receita_prato * 100, 2) if receita_prato else 0.0,
        "margem": round(receita_total - custo - custo_bebida, 2),
        "ticket_medio": round(receita_total / len(comandas), 2) if comandas else 0.0,
        "peso_medio_g": round(mean([p.peso_g for p in pesagens]), 0) if pesagens else 0.0,
        "mix_premium_pct": round(mean([p.mix_premium for p in pesagens]) * 100, 2)
        if pesagens
        else 0.0,
        "csat": round(mean([f.nota_geral for f in feedbacks]), 2) if feedbacks else 0.0,
        "feedbacks": len(feedbacks),
        "taxa_feedback_pct": round(len(feedbacks) / len(comandas) * 100, 1) if comandas else 0.0,
        "espera_p95_min": round(_p95([e.espera_estimada_min for e in eventos]), 2),
        "mesas_sujas": len(mesas_sujas),
        "mesa_suja_p95_min": round(_p95(minutos_sujas), 1) if minutos_sujas else 0.0,
    }


def ranking_itens(s, dias: int = 3) -> list[dict]:
    corte = datetime.now() - timedelta(days=dias)
    feedbacks = list(
        s.scalars(
            select(Feedback).where(
                Feedback.criado_em >= corte, Feedback.nota_item.is_not(None)
            )
        )
    )
    agrupado: dict[str, list[int]] = {}
    for f in feedbacks:
        if f.item_perguntado and f.nota_item:
            agrupado.setdefault(f.item_perguntado, []).append(f.nota_item)
    itens = [
        {
            "item": item,
            "nota_media": round(mean(notas), 2),
            "avaliacoes": len(notas),
        }
        for item, notas in agrupado.items()
    ]
    return sorted(itens, key=lambda i: (i["nota_media"], -i["avaliacoes"]))


def mix_satisfacao(s, dia: date | None = None) -> list[dict]:
    """Um ponto por comanda: mix premium (%) x nota geral. O cruzamento que eles não têm."""
    dia = dia or hoje()
    inicio, fim = _intervalo(dia)
    comandas = list(
        s.scalars(
            select(Comanda)
            .where(Comanda.aberta_em >= inicio, Comanda.aberta_em < fim)
            .options(selectinload(Comanda.pesagens).selectinload(Pesagem.itens),
                     selectinload(Comanda.feedbacks))
        )
    )
    pontos = []
    for c in comandas:
        if not c.feedbacks or not c.pesagens:
            continue
        premium = mean([p.mix_premium for p in c.pesagens]) * 100
        pontos.append(
            {
                "comanda": c.numero,
                "mix_premium_pct": round(premium, 1),
                "nota": c.feedbacks[-1].nota_geral,
                "cmv_pct": round(mean([p.cmv_pct for p in c.pesagens]), 1),
                "peso_g": sum(p.peso_g for p in c.pesagens),
            }
        )
    return pontos


def cmv_por_hora(s, dia: date | None = None) -> list[dict]:
    dia = dia or hoje()
    inicio, fim = _intervalo(dia)
    pesagens = list(
        s.scalars(select(Pesagem).where(Pesagem.criado_em >= inicio, Pesagem.criado_em < fim))
    )
    por_hora: dict[int, list[Pesagem]] = {}
    for p in pesagens:
        por_hora.setdefault(p.criado_em.hour, []).append(p)
    return [
        {
            "hora": f"{h:02d}h",
            "cmv_pct": round(mean([p.cmv_pct for p in lista]), 2),
            "pratos": len(lista),
            "mix_premium_pct": round(mean([p.mix_premium for p in lista]) * 100, 1),
        }
        for h, lista in sorted(por_hora.items())
    ]


# --------------------------------------------------------------------- filas


def fila_do_dia(s, dia: date | None = None) -> list[dict]:
    dia = dia or hoje()
    inicio, fim = _intervalo(dia)
    eventos = list(
        s.scalars(
            select(EventoFila)
            .where(EventoFila.criado_em >= inicio, EventoFila.criado_em < fim)
            .order_by(EventoFila.criado_em)
        )
    )
    return [
        {
            "hora": e.criado_em,
            "zona": e.zona,
            "pessoas": e.pessoas,
            "espera_min": e.espera_estimada_min,
        }
        for e in eventos
    ]


def fila_atual(s, dia: date | None = None) -> list[dict]:
    """Estado mais recente por zona.

    Fora do horário de serviço (ou em dia passado), usa o pico do dia (12h45) como
    referência — senão a demo à noite mostraria fila zero, que não conta a história.
    """
    dia = dia or hoje()
    eventos = fila_do_dia(s, dia)
    if not eventos:
        return []

    referencia = datetime.now()
    inicio = datetime.combine(dia, time(11, 30))
    fim = datetime.combine(dia, time(15, 30))
    if dia != hoje() or not (inicio <= referencia <= fim):
        referencia = datetime.combine(dia, time(12, 45))

    ultimos: dict[str, dict] = {}
    for ev in eventos:
        if ev["hora"] <= referencia:
            ultimos[ev["zona"]] = ev
    if not ultimos:
        for ev in eventos:
            ultimos.setdefault(ev["zona"], ev)

    # Padroniza o nome usado pelas regras de alerta.
    return [
        {**ev, "espera_estimada_min": ev["espera_min"]} for ev in ultimos.values()
    ]


# --------------------------------------------------------------------- mesas


def mesas_com_tempo(s) -> list[dict]:
    agora = datetime.now()
    saida = []
    for mesa in s.scalars(select(Mesa).order_by(Mesa.id)):
        minutos_livre = (
            (agora - mesa.livre_desde).total_seconds() / 60
            if mesa.livre_desde and mesa.status in ("livre", "suja")
            else None
        )
        minutos_ocupada = (
            (agora - mesa.ocupada_desde).total_seconds() / 60
            if mesa.ocupada_desde and mesa.status == "ocupada"
            else None
        )
        saida.append(
            {
                "id": mesa.id,
                "nivel": mesa.nivel,
                "lugares": mesa.lugares,
                "status": mesa.status,
                "minutos_livre": round(minutos_livre or 0, 1),
                "minutos_ocupada": round(minutos_ocupada or 0, 1),
                "prioridade": prioridade_mesa(minutos_livre or 0, mesa.lugares, mesa.nivel)
                if mesa.status == "suja"
                else 0.0,
            }
        )
    return saida


def mesas_sujas(s) -> list[dict]:
    return [m for m in mesas_com_tempo(s) if m["status"] == "suja"]


def ranking_higienizacao(s, limite: int = 5) -> list[dict]:
    return sorted(mesas_sujas(s), key=lambda m: m["prioridade"], reverse=True)[:limite]


def mudar_status_mesa(s, mesa_id: int, status: str) -> None:
    mesa = s.get(Mesa, mesa_id)
    if not mesa:
        return
    agora = datetime.now()
    mesa.status = status
    if status == "ocupada":
        mesa.ocupada_desde = agora
        mesa.livre_desde = None
    elif status == "suja":
        mesa.livre_desde = agora
        mesa.ocupada_desde = None
    elif status == "livre":
        mesa.livre_desde = agora
        mesa.ocupada_desde = None
        mesa.higienizada_em = agora
    s.flush()


# --------------------------------------------------------------------- cubas


def reposicoes_do_dia(s, dia: date | None = None) -> list[dict]:
    dia = dia or hoje()
    inicio, fim = _intervalo(dia)
    reposicoes = list(
        s.scalars(
            select(ReposicaoCuba).where(
                ReposicaoCuba.criado_em >= inicio, ReposicaoCuba.criado_em < fim
            )
        )
    )
    agrupado: dict[str, dict] = {}
    for r in reposicoes:
        registro = agrupado.setdefault(
            r.item, {"item": r.item, "reposicoes": 0, "capacidade_kg": r.capacidade_kg}
        )
        registro["reposicoes"] += 1
    for registro in agrupado.values():
        registro["kg_estimado"] = round(registro["reposicoes"] * registro["capacidade_kg"], 1)
    return sorted(agrupado.values(), key=lambda r: r["reposicoes"], reverse=True)


def registrar_reposicao(s, item: str, capacidade_kg: float, operador: str = "cozinha") -> None:
    s.add(ReposicaoCuba(item=item, capacidade_kg=capacidade_kg, operador=operador))
    s.flush()


# ------------------------------------------------------------------ feedback


def pergunta_do_dia(s) -> dict:
    itens = ranking_itens(s, dias=3)
    if itens:
        pior = itens[0]
        return {
            "item": pior["item"],
            "nota_media": pior["nota_media"],
            "avaliacoes": pior["avaliacoes"],
            "motivo": "menor nota dos últimos 3 dias",
        }
    return {
        "item": "lasanha",
        "nota_media": 0.0,
        "avaliacoes": 0,
        "motivo": "item estratégico (baixo giro)",
    }


def registrar_feedback(
    s,
    comanda_numero: str,
    nota_geral: int,
    item: str | None = None,
    nota_item: int | None = None,
    resto: str | None = None,
    comentario: str | None = None,
    canal: str = "totem",
) -> None:
    s.add(
        Feedback(
            comanda_numero=comanda_numero,
            nota_geral=nota_geral,
            item_perguntado=item,
            nota_item=nota_item,
            resto=resto,
            comentario=comentario,
            canal=canal,
        )
    )
    s.flush()


# ------------------------------------------------------------------ comandas


def proximo_numero(s) -> str:
    numeros = [int(n) for n in s.scalars(select(Comanda.numero))]
    return f"{(max(numeros) + 1) if numeros else 1:04d}"


def criar_comanda(s, numero: str | None = None, pessoas: int = 2) -> str:
    numero = numero or proximo_numero(s)
    if s.get(Comanda, numero):
        return numero
    s.add(
        Comanda(
            numero=numero,
            codigo_barras=f"789{numero}",
            origem="simulado",
            aberta_em=datetime.now(),
            pessoas=pessoas,
        )
    )
    s.flush()
    return numero


def listar_comandas(s, dia: date | None = None, limite: int = 300) -> list[dict]:
    dia = dia or hoje()
    inicio, fim = _intervalo(dia)
    comandas = list(
        s.scalars(
            select(Comanda)
            .where(Comanda.aberta_em >= inicio, Comanda.aberta_em < fim)
            .order_by(Comanda.aberta_em.desc())
            .limit(limite)
            .options(
                selectinload(Comanda.pesagens).selectinload(Pesagem.itens),
                selectinload(Comanda.feedbacks),
            )
        )
    )
    saida = []
    for c in comandas:
        receita = sum(p.receita_prato for p in c.pesagens)
        custo = sum(p.custo_estimado for p in c.pesagens)
        saida.append(
            {
                "comanda": c.numero,
                "hora": c.aberta_em.strftime("%H:%M"),
                "pessoas": c.pessoas,
                "pratos": len(c.pesagens),
                "peso_g": sum(p.peso_g for p in c.pesagens),
                "receita": round(receita + c.bebidas_valor, 2),
                "cmv_pct": round(custo / receita * 100, 1) if receita else 0.0,
                "nota": c.feedbacks[-1].nota_geral if c.feedbacks else None,
                "status": "fechada" if c.fechada_em else "aberta",
            }
        )
    return saida


def resumo_comanda(s, numero: str) -> dict | None:
    comanda = s.get(
        Comanda,
        numero,
        options=[
            selectinload(Comanda.pesagens).selectinload(Pesagem.itens),
            selectinload(Comanda.feedbacks),
        ],
    )
    if not comanda:
        return None

    pratos = []
    for p in comanda.pesagens:
        pratos.append(
            {
                "id": p.id,
                "hora": p.criado_em.strftime("%H:%M"),
                "peso_g": p.peso_g,
                "cmv_pct": p.cmv_pct,
                "custo": p.custo_estimado,
                "receita": p.receita_prato,
                "margem": round(p.receita_prato - p.custo_estimado, 2),
                "mix_premium_pct": round(p.mix_premium * 100, 1),
                "modelo": p.modelo,
                "foto_path": p.foto_path,
                "itens": [
                    {
                        "categoria": i.categoria,
                        "rotulo": i.rotulo,
                        "percentual": i.percentual_area,
                        "peso_g": i.peso_estimado_g,
                        "custo": i.custo,
                    }
                    for i in sorted(p.itens, key=lambda x: x.peso_estimado_g, reverse=True)
                ],
            }
        )

    receita_prato = sum(p["receita"] for p in pratos)
    custo_prato = sum(p["custo"] for p in pratos)
    receita_total = receita_prato + comanda.bebidas_valor
    custo_total = custo_prato + comanda.bebidas_valor * 0.30

    return {
        "numero": comanda.numero,
        "aberta_em": comanda.aberta_em,
        "fechada_em": comanda.fechada_em,
        "pessoas": comanda.pessoas,
        "bebidas": round(comanda.bebidas_valor, 2),
        "valor_pago": comanda.valor_pago,
        "pratos": pratos,
        "feedbacks": [
            {
                "hora": f.criado_em.strftime("%H:%M"),
                "nota_geral": f.nota_geral,
                "item": f.item_perguntado,
                "nota_item": f.nota_item,
                "resto": f.resto,
                "canal": f.canal,
            }
            for f in comanda.feedbacks
        ],
        "totais": {
            "receita": round(receita_total, 2),
            "custo": round(custo_total, 2),
            "margem": round(receita_total - custo_total, 2),
            "cmv_pct": round(custo_total / receita_total * 100, 2) if receita_total else 0.0,
        },
    }


# ------------------------------------------------------------------- alertas


def contexto_alertas(s, dia: date | None = None) -> dict:
    ind = indicadores(s, dia)
    return {
        "fila": fila_atual(s, dia),
        "mesas_sujas": mesas_sujas(s),
        "cmv_pct": ind["cmv_pct"],
        "mix_premium_pct": ind["mix_premium_pct"] / 100,
        "itens": ranking_itens(s, dias=3),
    }


def alertas_atuais(s, dia: date | None = None) -> list[dict]:
    return gerar_alertas(contexto_alertas(s, dia))


def registrar_alertas(s, alertas: list[dict], cooldown_min: int = 15) -> int:
    """Persiste alertas novos respeitando cooldown por (tipo, entidade)."""
    corte = datetime.now() - timedelta(minutes=cooldown_min)
    recentes = list(
        s.scalars(select(Alerta).where(Alerta.criado_em >= corte, Alerta.resolvido_em.is_(None)))
    )
    chaves = {(a.tipo, a.entidade) for a in recentes}
    novos = 0
    for alerta in alertas:
        chave = (alerta["tipo"], alerta["entidade"])
        if chave in chaves:
            continue
        s.add(Alerta(**alerta))
        chaves.add(chave)
        novos += 1
    s.flush()
    return novos
