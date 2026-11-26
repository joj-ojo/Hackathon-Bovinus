"""Pratos de demonstração: imagens sintéticas + CMV esperado.

Serve para dois propósitos:
1. a demo funciona sem internet e sem chave de API (as imagens são analisadas
   pelo pipeline real, em modo heurístico);
2. a comparação "mesmo peso, margens diferentes" vira um slide do pitch.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from core.cmv import calcular_cmv
from core.config import PRATOS_DIR, settings
from core.custos import CATEGORIAS_PADRAO

PRATOS_DEMO: list[dict] = [
    {
        "nome": "churrasco",
        "titulo": "Prato de churrasco",
        "descricao": "Picanha, costela e acompanhamentos — o mix que derruba a margem.",
        "peso_g": 620,
        "mix": {
            "carne_premium": 0.34,
            "carne_media": 0.16,
            "ave_suino": 0.05,
            "acompanhamento": 0.18,
            "salada_legume": 0.14,
            "sobremesa": 0.04,
            "massa_risoto": 0.07,
            "fritura_empanado": 0.02,
        },
    },
    {
        "nome": "equilibrado",
        "titulo": "Prato equilibrado",
        "descricao": "O alvo operacional: proteína, carboidrato e salada em proporção saudável.",
        "peso_g": 540,
        "mix": {
            "carne_premium": 0.10,
            "carne_media": 0.10,
            "ave_suino": 0.10,
            "acompanhamento": 0.30,
            "salada_legume": 0.28,
            "sobremesa": 0.06,
            "massa_risoto": 0.04,
            "fritura_empanado": 0.02,
        },
    },
    {
        "nome": "carboidrato",
        "titulo": "Prato de arroz e feijão",
        "descricao": "Barato para o cliente, caro para o salão: ocupa o prato e não gera margem.",
        "peso_g": 700,
        "mix": {
            "carne_premium": 0.02,
            "carne_media": 0.03,
            "ave_suino": 0.05,
            "acompanhamento": 0.50,
            "salada_legume": 0.30,
            "sobremesa": 0.05,
            "massa_risoto": 0.03,
            "fritura_empanado": 0.02,
        },
    },
]


def _cor(categoria: str) -> tuple[int, int, int]:
    hexcor = CATEGORIAS_PADRAO.get(categoria, {}).get("cor", "#999999").lstrip("#")
    return int(hexcor[0:2], 16), int(hexcor[2:4], 16), int(hexcor[4:6], 16)


def _variar(cor: tuple[int, int, int], rng: random.Random, amplitude: int = 26):
    return tuple(max(0, min(255, c + rng.randint(-amplitude, amplitude))) for c in cor)


def _desenhar_prato(caminho: Path, mix: dict[str, float], seed: int, tamanho: int = 900) -> Path:
    """Desenha um prato visto de cima, com cada categoria em um setor."""
    from PIL import Image, ImageDraw, ImageFilter

    rng = random.Random(seed)
    img = Image.new("RGB", (tamanho, tamanho), (58, 54, 52))
    draw = ImageDraw.Draw(img)

    cx = cy = tamanho // 2
    raio = int(tamanho * 0.46)
    # Sombra e louça
    draw.ellipse(
        [cx - raio - 8, cy - raio - 6, cx + raio + 8, cy + raio + 14], fill=(40, 38, 37)
    )
    draw.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill=(238, 236, 231))
    draw.ellipse(
        [cx - raio + 10, cy - raio + 10, cx + raio - 10, cy + raio - 10],
        fill=(250, 249, 246),
        outline=(224, 221, 214),
        width=3,
    )

    raio_comida = int(raio * 0.80)
    area_comida = math.pi * raio_comida**2

    angulo_inicial = rng.uniform(0, 2 * math.pi)
    total = sum(mix.values()) or 1.0

    for categoria, pct in sorted(mix.items(), key=lambda kv: kv[1], reverse=True):
        fracao = pct / total
        setor = fracao * 2 * math.pi
        area_categoria = area_comida * fracao
        n_blobs = max(4, int(fracao * 26))
        raio_blob = max(9.0, math.sqrt(area_categoria / (n_blobs * math.pi)) * 1.15)
        cor_base = _cor(categoria)

        for _ in range(n_blobs):
            angulo = angulo_inicial + rng.uniform(0.06, 0.94) * setor
            distancia = rng.uniform(0.18, 0.80) * raio_comida
            bx = cx + math.cos(angulo) * distancia
            by = cy + math.sin(angulo) * distancia
            rb = raio_blob * rng.uniform(0.72, 1.35)
            # massa do alimento
            draw.ellipse(
                [bx - rb, by - rb, bx + rb, by + rb], fill=_variar(cor_base, rng, 18)
            )
            # textura (pedaços, grãos, folhas)
            for _ in range(9):
                tx = bx + rng.gauss(0, rb * 0.45)
                ty = by + rng.gauss(0, rb * 0.45)
                tr = rb * rng.uniform(0.10, 0.28)
                draw.ellipse(
                    [tx - tr, ty - tr, tx + tr, ty + tr],
                    fill=_variar(cor_base, rng, 34),
                )

        angulo_inicial += setor

    # Molho/brilho leve para não ficar chapado
    brilho = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    img = Image.blend(img, brilho, 0.18)

    caminho.parent.mkdir(parents=True, exist_ok=True)
    img.save(caminho, format="JPEG", quality=88)
    return caminho


def gerar_todas(forcar: bool = False) -> list[dict]:
    """Garante que as três imagens existem e devolve a lista com caminho e CMV."""
    saida = []
    for indice, prato in enumerate(PRATOS_DEMO):
        caminho = PRATOS_DIR / f"prato_{prato['nome']}.jpg"
        if forcar or not caminho.exists():
            _desenhar_prato(caminho, prato["mix"], seed=100 + indice)
        resultado = calcular_cmv(
            prato["peso_g"],
            [
                {"categoria": c, "percentual_area": p, "rotulo": ""}
                for c, p in prato["mix"].items()
            ],
            settings.preco_kg,
        )
        saida.append(
            {
                **prato,
                "caminho": caminho,
                "cmv": resultado.como_dict()["cmv"],
                "mix_premium_pct": round(resultado.mix_premium_pct * 100, 1),
            }
        )
    return saida
