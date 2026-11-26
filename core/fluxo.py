"""Fila, lei de Little e priorização de mesas.

Little's Law: W = L / λ  (espera = pessoas na fila / taxa de chegada).
Serve para transformar "tem fila" em "a fila custa 4 minutos".
"""

from __future__ import annotations

# Limiares operacionais calibrados com o que foi dito na palestra.
META_CHURRASQUEIRA_MIN = 2.5
META_ENTRADA_MIN = 2.0
META_LIMPEZA_MIN = 3.0
ALERTA_ESCADA_PESSOAS = 12  # acima disso a fila chega na escada da entrada


def espera_estimada(pessoas: float, chegadas_por_min: float) -> float:
    """Tempo médio de espera em minutos (Lei de Little)."""
    if chegadas_por_min <= 0:
        return 0.0
    return max(0.0, pessoas / chegadas_por_min)


def fila_maxima(chegadas_por_min: float, meta_min: float) -> int:
    """Quantas pessoas cabem na fila para respeitar a meta de espera."""
    return int(round(chegadas_por_min * meta_min))


def severidade_fila(zona: str, pessoas: int, espera_min: float) -> str | None:
    """Classifica o estado da fila em critica/alta/media ou None."""
    if zona == "entrada":
        if pessoas >= ALERTA_ESCADA_PESSOAS or espera_min >= 3.0:
            return "critica"
        if pessoas >= ALERTA_ESCADA_PESSOAS * 0.7:
            return "alta"
    elif zona == "churrasqueira":
        if espera_min >= META_CHURRASQUEIRA_MIN * 1.6:
            return "critica"
        if espera_min >= META_CHURRASQUEIRA_MIN:
            return "alta"
    elif zona == "caixa" and espera_min >= 3.0:
        return "media"
    return None


def prioridade_mesa(minutos_livre: float, lugares: int, nivel: str) -> float:
    """Score de prioridade de higienização: tempo pesa mais, mas mesa grande e
    no salão principal vale mais (é onde estão os grupos e o pico)."""
    fator_nivel = 1.15 if nivel == "principal" else 1.0
    return round(minutos_livre * (lugares / 4.0) * fator_nivel, 2)


def cor_mesa(minutos_livre: float) -> str:
    if minutos_livre >= META_LIMPEZA_MIN * 2:
        return "#B42318"
    if minutos_livre >= META_LIMPEZA_MIN:
        return "#B54708"
    return "#B7C4B0"
