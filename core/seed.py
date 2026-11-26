"""Seed sintético do demo: 3 dias de operação coerentes com a palestra.

Tudo é rotulado como sintético na interface. O objetivo é ter volume suficiente
para as telas contarem uma história (pico 12h10–13h20, quarta de feijoada,
lasanha com nota ruim) sem depender de dados reais do cliente.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select

from core.cmv import calcular_cmv
from core.config import settings
from core.db import sessao
from core.fluxo import espera_estimada
from core.models import (
    Comanda,
    EventoFila,
    Feedback,
    Mesa,
    Pesagem,
    PesagemItem,
    ReposicaoCuba,
)

RNG_SEED = 42

# Perfis de prato: qual a chance de o cliente montar cada combinação.
PERFIS: dict[str, tuple[float, dict[str, float]]] = {
    "equilibrado": (
        0.28,
        {
            "carne_premium": 0.12,
            "carne_media": 0.12,
            "ave_suino": 0.10,
            "acompanhamento": 0.30,
            "salada_legume": 0.24,
            "sobremesa": 0.06,
            "massa_risoto": 0.04,
            "fritura_empanado": 0.02,
        },
    ),
    "churrasco": (
        0.22,
        {
            "carne_premium": 0.42,
            "carne_media": 0.18,
            "ave_suino": 0.06,
            "acompanhamento": 0.14,
            "salada_legume": 0.12,
            "sobremesa": 0.04,
            "massa_risoto": 0.02,
            "fritura_empanado": 0.02,
        },
    ),
    "carboidrato": (
        0.20,
        {
            "carne_premium": 0.04,
            "carne_media": 0.04,
            "ave_suino": 0.06,
            "acompanhamento": 0.48,
            "salada_legume": 0.24,
            "sobremesa": 0.04,
            "massa_risoto": 0.08,
            "fritura_empanado": 0.02,
        },
    ),
    "salada": (
        0.16,
        {
            "carne_premium": 0.05,
            "carne_media": 0.03,
            "ave_suino": 0.07,
            "acompanhamento": 0.15,
            "salada_legume": 0.58,
            "sobremesa": 0.06,
            "massa_risoto": 0.04,
            "fritura_empanado": 0.02,
        },
    ),
    "massa": (
        0.14,
        {
            "carne_premium": 0.05,
            "carne_media": 0.05,
            "ave_suino": 0.08,
            "acompanhamento": 0.18,
            "salada_legume": 0.16,
            "sobremesa": 0.06,
            "massa_risoto": 0.40,
            "fritura_empanado": 0.02,
        },
    ),
}

# Itens da "Pergunta do Dia" com a nota que o público dá (é o enredo do painel).
ITENS_PERGUNTA: dict[str, float] = {
    "lasanha": 2.05,
    "frutos do mar": 2.55,
    "feijoada": 3.20,
    "arroz branco": 2.95,
    "salada de grão-de-bico": 3.10,
    "picanha": 3.75,
    "costela": 3.55,
}

BEBIDAS = [0.0, 0.0, 0.0, 6.0, 8.0, 8.0, 12.0, 14.0, 18.0]

CUBAS = {
    "arroz branco": (5, 10.0),
    "feijão": (3, 10.0),
    "picanha": (4, 6.0),
    "costela": (3, 6.0),
    "lasanha": (1, 8.0),
    "salada de grão-de-bico": (2, 5.0),
    "farofa": (2, 4.0),
}


def _perfil(rng: random.Random) -> dict[str, float]:
    nomes = list(PERFIS)
    pesos = [PERFIS[n][0] for n in nomes]
    escolhido = rng.choices(nomes, weights=pesos, k=1)[0]
    return dict(PERFIS[escolhido][1])


def _com_jitter(rng: random.Random, mix: dict[str, float]) -> dict[str, float]:
    """Variação natural: ninguém monta exatamente o mesmo prato."""
    ajustado = {}
    for cat, pct in mix.items():
        if rng.random() < 0.15:
            continue  # às vezes o cliente não pega aquela categoria
        ajustado[cat] = max(0.01, pct * rng.uniform(0.75, 1.25))
    total = sum(ajustado.values())
    return {k: v / total for k, v in ajustado.items()}


def _hora_chegada(rng: random.Random, dia: date) -> datetime:
    if rng.random() < 0.72:
        minutos = rng.gauss(12 * 60 + 50, 21)  # pico 12h10–13h20
    else:
        minutos = rng.uniform(11 * 60 + 30, 15 * 60 + 15)
    minutos = min(max(minutos, 11 * 60 + 30), 15 * 60 + 20)
    return datetime.combine(dia, time(0)) + timedelta(minutes=minutos)


def _curva(minuto_do_dia: float, centro: float = 785.0, largura: float = 34.0) -> float:
    import math

    return math.exp(-((minuto_do_dia - centro) ** 2) / (2 * largura**2))


def _ja_populado(s) -> bool:
    return (s.scalar(select(func.count()).select_from(Comanda)) or 0) > 0


def popular(force: bool = False) -> bool:
    """Cria 3 dias de dados. Idempotente. Retorna True se inseriu algo."""
    with sessao() as s:
        if _ja_populado(s) and not force:
            return False
        if force:
            for modelo in (PesagemItem, Pesagem, Feedback, Comanda, Mesa, EventoFila, ReposicaoCuba):
                s.query(modelo).delete()
            s.flush()

        rng = random.Random(RNG_SEED)
        hoje = date.today()
        dias = [hoje - timedelta(days=2), hoje - timedelta(days=1), hoje]
        agora = datetime.now()

        for indice_dia, dia in enumerate(dias):
            base = indice_dia * 200
            for i in range(settings.seed_comandas_por_dia):
                numero = f"{base + i + 1:04d}"
                aberta = _hora_chegada(rng, dia)
                peso = min(1050, max(250, rng.gauss(560, 85)))
                mix = _com_jitter(rng, _perfil(rng))
                itens = [
                    {"categoria": cat, "percentual_area": pct, "rotulo": ""}
                    for cat, pct in mix.items()
                ]
                resultado = calcular_cmv(peso, itens, settings.preco_kg)
                bebidas = rng.choice(BEBIDAS)

                fechada = None
                valor_pago = None
                if dia < hoje or rng.random() < 0.55:
                    fechada = aberta + timedelta(minutes=rng.uniform(24, 52))
                    valor_pago = round(resultado.receita + bebidas, 2)

                s.add(
                    Comanda(
                        numero=numero,
                        codigo_barras=f"789{numero}",
                        origem="simulado",
                        aberta_em=aberta,
                        fechada_em=fechada,
                        pessoas=rng.choices([1, 2, 3, 4, 6], [0.32, 0.34, 0.16, 0.12, 0.06])[0],
                        bebidas_valor=bebidas,
                        valor_pago=valor_pago,
                    )
                )

                pesagem = Pesagem(
                    id=f"{indice_dia}{i:05d}{rng.randrange(1000):03d}",
                    comanda_numero=numero,
                    balanca_id=rng.choice(["B1", "B2", "B3"]),
                    peso_g=int(peso),
                    preco_kg=settings.preco_kg,
                    foto_path=None,
                    modelo="simulado",
                    confianca=0.82,
                    custo_estimado=resultado.custo_total,
                    receita_prato=resultado.receita,
                    cmv_pct=resultado.cmv_pct,
                    criado_em=aberta + timedelta(minutes=rng.uniform(4, 9)),
                )
                for item in resultado.itens:
                    pesagem.itens.append(
                        PesagemItem(
                            categoria=item["categoria"],
                            rotulo=item["rotulo"],
                            percentual_area=item["percentual_area"],
                            peso_estimado_g=item["peso_estimado_g"],
                            custo_kg=item["custo_kg"],
                            custo=item["custo"],
                            confianca=0.82,
                        )
                    )
                s.add(pesagem)

                # Feedback em ~38% das comandas, com viés por perfil do prato.
                if rng.random() < 0.38:
                    base_nota = {
                        "churrasco": 3.5,
                        "equilibrado": 3.2,
                        "massa": 2.8,
                        "salada": 3.0,
                        "carboidrato": 2.9,
                    }[_perfil_proximo(mix)]
                    nota_geral = max(1, min(4, round(rng.gauss(base_nota, 0.65))))
                    item = rng.choices(
                        list(ITENS_PERGUNTA),
                        weights=[0.22, 0.12, 0.16, 0.14, 0.10, 0.16, 0.10],
                        k=1,
                    )[0]
                    nota_item = max(1, min(4, round(rng.gauss(ITENS_PERGUNTA[item], 0.7))))
                    s.add(
                        Feedback(
                            comanda_numero=numero,
                            nota_geral=nota_geral,
                            item_perguntado=item,
                            nota_item=nota_item,
                            resto=rng.choices(["nada", "pouco", "muito"], [0.55, 0.33, 0.12])[0],
                            comentario=None,
                            canal=rng.choice(["totem", "qr"]),
                            criado_em=(fechada or aberta) + timedelta(minutes=rng.uniform(0, 3)),
                        )
                    )

            # Fila: amostra a cada 2 minutos ao longo do serviço.
            amplitudes = {"entrada": 17.0, "churrasqueira": 34.0, "caixa": 7.0}
            chegadas_pico = {"entrada": 8.6, "churrasqueira": 8.6, "caixa": 4.2}
            for minuto in range(11 * 60 + 30, 15 * 60 + 30, 2):
                curva = _curva(minuto)
                for zona, amp in amplitudes.items():
                    desvio = max(0.5, 1.7 * curva)
                    pessoas = max(0, round(rng.gauss(amp * curva, desvio)))
                    chegadas = max(0.0, chegadas_pico[zona] * curva + rng.gauss(0, 0.25))
                    s.add(
                        EventoFila(
                            zona=zona,
                            pessoas=pessoas,
                            chegadas_por_min=round(chegadas, 2),
                            espera_estimada_min=round(espera_estimada(pessoas, chegadas), 2)
                            if chegadas >= 0.5
                            else 0.0,
                            criado_em=datetime.combine(dia, time(0)) + timedelta(minutes=minuto),
                        )
                    )

            # Cubas repostas ao longo do pico.
            for item, (vezes, capacidade) in CUBAS.items():
                for _ in range(vezes):
                    s.add(
                        ReposicaoCuba(
                            item=item,
                            capacidade_kg=capacidade,
                            operador=rng.choice(["cozinha", "churrasqueira"]),
                            criado_em=datetime.combine(dia, time(0))
                            + timedelta(minutes=rng.uniform(11 * 60 + 40, 14 * 60 + 30)),
                        )
                    )

        # Mesas: subconjunto visível pelas câmeras (o salão tem 90).
        if not s.scalar(select(func.count()).select_from(Mesa)):
            for mesa_id in range(1, 41):
                nivel = "principal" if mesa_id <= 24 else "superior"
                lugares = rng.choices([2, 4, 6, 8], [0.2, 0.45, 0.25, 0.10])[0]
                sorte = rng.random()
                if sorte < 0.55:
                    status, ocupada, livre = "ocupada", agora - timedelta(minutes=rng.uniform(6, 42)), None
                elif sorte < 0.82:
                    status, ocupada, livre = "livre", None, agora - timedelta(minutes=rng.uniform(0, 2))
                else:
                    status, ocupada, livre = (
                        "suja",
                        None,
                        agora - timedelta(minutes=rng.uniform(1, 9)),
                    )
                s.add(
                    Mesa(
                        id=mesa_id,
                        nivel=nivel,
                        lugares=lugares,
                        status=status,
                        ocupada_desde=ocupada,
                        livre_desde=livre,
                    )
                )

    return True


def _perfil_proximo(mix: dict[str, float]) -> str:
    """Qual perfil de referência está mais próximo do prato gerado."""
    melhor, menor_distancia = "equilibrado", 9.9
    for nome, (_, referencia) in PERFIS.items():
        distancia = sum(
            abs(mix.get(cat, 0.0) - referencia.get(cat, 0.0)) for cat in set(mix) | set(referencia)
        )
        if distancia < menor_distancia:
            melhor, menor_distancia = nome, distancia
    return melhor
