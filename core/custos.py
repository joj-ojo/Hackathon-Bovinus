"""Tabela de custo por categoria e densidade superficial (g/cm²).

Premissa explícita: o restaurante não usa ficha técnica no dia a dia, então estes
valores são estimativas de atacado/CEASA, editáveis na interface. Documentar isso
no pitch é mais forte do que fingir precisão que não existe.
"""

from __future__ import annotations

CATEGORIAS_PADRAO: dict[str, dict] = {
    "carne_premium": {
        "rotulo": "Carne premium (picanha, filé, maminha)",
        "custo_kg": 79.0,
        "densidade": 1.55,
        "cor": "#8B1E2D",
    },
    "carne_media": {
        "rotulo": "Carne média (costela, cupim, alcatra)",
        "custo_kg": 45.0,
        "densidade": 1.40,
        "cor": "#B4531F",
    },
    "ave_suino": {
        "rotulo": "Ave/suíno (frango, linguiça, lombo)",
        "custo_kg": 22.0,
        "densidade": 1.25,
        "cor": "#D08A4A",
    },
    "acompanhamento": {
        "rotulo": "Acompanhamento (arroz, feijão, farofa, purê)",
        "custo_kg": 12.0,
        "densidade": 1.10,
        "cor": "#E6D2A8",
    },
    "massa_risoto": {
        "rotulo": "Massa/risoto",
        "custo_kg": 18.0,
        "densidade": 1.00,
        "cor": "#D9B26A",
    },
    "fritura_empanado": {
        "rotulo": "Fritura/empanado",
        "custo_kg": 25.0,
        "densidade": 0.90,
        "cor": "#C98B2E",
    },
    "salada_legume": {
        "rotulo": "Salada/legume",
        "custo_kg": 16.0,
        "densidade": 0.55,
        "cor": "#3F7D3A",
    },
    "sobremesa": {
        "rotulo": "Sobremesa",
        "custo_kg": 28.0,
        "densidade": 1.15,
        "cor": "#A64B7A",
    },
    "outros": {
        "rotulo": "Outros/não identificado",
        "custo_kg": 18.0,
        "densidade": 1.00,
        "cor": "#9A9A9A",
    },
}

# Vocabulário que o VLM recebe. Mantenha em sincronia com CATEGORIAS_PADRAO.
LISTA_CATEGORIAS = [c for c in CATEGORIAS_PADRAO if c != "outros"]

ROTULOS_EXEMPLO: dict[str, list[str]] = {
    "carne_premium": ["picanha", "filé mignon", "maminha", "contrafilé"],
    "carne_media": ["costela", "cupim", "alcatra", "fraldinha"],
    "ave_suino": ["frango grelhado", "linguiça", "lombo", "frango à passarinho"],
    "acompanhamento": ["arroz branco", "feijão", "farofa", "purê de batata"],
    "massa_risoto": ["lasanha", "penne", "risoto", "nhoque"],
    "fritura_empanado": ["à milanesa", "bolinho", "batata frita", "polenta frita"],
    "salada_legume": ["alface e tomate", "salada de grão-de-bico", "brócolis", "cenoura"],
    "sobremesa": ["pudim", "mousse", "fruta", "bolo"],
    "outros": ["item não identificado"],
}


def dicionario_categorias(categorias_db) -> dict[str, dict]:
    """Converte as linhas do banco no dicionário usado pelo motor de CMV."""
    if not categorias_db:
        return dict(CATEGORIAS_PADRAO)
    return {
        c.categoria: {
            "rotulo": c.rotulo,
            "custo_kg": c.custo_kg,
            "densidade": c.densidade,
            "cor": c.cor,
        }
        for c in categorias_db
    }
