"""Detector heurístico (offline): segmenta o prato e estima a composição por cor.

Não é tão preciso quanto um VLM ou um modelo treinado — a função dele é garantir
que a demonstração nunca fique sem resposta, mesmo sem internet.
"""

from __future__ import annotations

import cv2
import numpy as np

from core.custos import CATEGORIAS_PADRAO

# Rótulos de exemplo por categoria, usados quando só a cor é conhecida.
_ROTULO_GENERICO = {
    "carne_premium": "carne vermelha",
    "carne_media": "carne assada",
    "ave_suino": "ave/embutido",
    "acompanhamento": "arroz/acompanhamento",
    "massa_risoto": "massa",
    "fritura_empanado": "empanado",
    "salada_legume": "salada",
    "sobremesa": "sobremesa",
    "outros": "não identificado",
}


def _hex_para_bgr(hexcor: str) -> tuple[int, int, int]:
    h = hexcor.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


def _detectar_circulo_prato(img: np.ndarray) -> tuple[int, int, int]:
    """Tenta achar o prato por Hough; se falhar, assume círculo central."""
    h, w = img.shape[:2]
    menor = min(h, w)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    circulos = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=menor,
        param1=110,
        param2=55,
        minRadius=int(menor * 0.28),
        maxRadius=int(menor * 0.55),
    )
    if circulos is not None and len(circulos[0]):
        x, y, r = max(circulos[0], key=lambda c: c[2])
        return int(x), int(y), int(r)
    return w // 2, h // 2, int(menor * 0.44)


def _classificar_cor(bgr: tuple[int, int, int]) -> str:
    """Mapeia a cor média de um agrupamento para uma categoria de custo.

    As faixas abaixo foram calibradas com as cores de referência das categorias
    e com fotos de buffet (arroz esbranquiçado, dourados de fritura, vermelhos
    escuros de carne). É heurística: serve para não deixar a demo sem resposta.
    """
    pixel = np.uint8([[bgr]])
    h, s, v = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0][0]
    h, s, v = int(h), int(s), int(v)

    # Verdes: saladas e legumes
    if 40 <= h <= 100 and s >= 55:
        return "salada_legume"

    # Vermelhos, vinhos e rosados
    if h <= 6 or h >= 148:
        if s < 60:
            return "outros"
        if h >= 170 and s >= 120:
            return "carne_premium"
        if 155 <= h < 170 and s >= 120 and v >= 150:
            return "sobremesa"
        if v < 150 and s >= 110:
            return "carne_premium"
        return "carne_media"

    # Marrons escuros: carne assada, não confundir com massa
    if 7 <= h <= 39 and s >= 80:
        if v < 130:
            return "carne_media"
        if v < 165:
            return "ave_suino"

    # Beges e claros: arroz, feijão claro, farofa
    if s < 45:
        return "acompanhamento" if v > 165 else "outros"
    if s < 105:
        if v >= 195:
            return "acompanhamento"
        return "massa_risoto" if v >= 160 else "outros"
    if s < 145:
        return "massa_risoto"

    # Saturados quentes: aves, frituras e carnes
    if h <= 24:
        return "ave_suino" if v >= 185 else "carne_media"
    if h <= 31:
        return "ave_suino"
    return "fritura_empanado"


def analisar(img_bytes: bytes) -> dict:
    """Retorna {itens, overlay_png, confianca_global} ou itens vazios se não houver comida."""
    buffer = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if img is None:
        return {"itens": [], "overlay_png": None, "confianca_global": 0.0}

    # Normaliza o tamanho: 640px é suficiente e mantém a inferência barata.
    h, w = img.shape[:2]
    escala = 640 / max(h, w)
    if escala < 1:
        img = cv2.resize(img, (int(w * escala), int(h * escala)), interpolation=cv2.INTER_AREA)

    cx, cy, r = _detectar_circulo_prato(img)
    h, w = img.shape[:2]

    mascara = np.zeros((h, w), np.uint8)
    cv2.circle(mascara, (cx, cy), r, 255, -1)

    # Cor do prato vazio: anel interno (a louça aparece na borda).
    anel = np.zeros((h, w), np.uint8)
    cv2.circle(anel, (cx, cy), r, 255, -1)
    cv2.circle(anel, (cx, cy), int(r * 0.94), 0, -1)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    pixels_anel = lab[anel > 0]
    cor_prato = np.median(pixels_anel, axis=0) if len(pixels_anel) else np.array([235, 128, 128])

    pixels = lab[mascara > 0].reshape(-1, 3).astype(np.float32)
    if len(pixels) < 500:
        return {"itens": [], "overlay_png": None, "confianca_global": 0.0}

    k = min(6, max(3, len(pixels) // 800))
    criterio = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5)
    _, rotulos, centros = cv2.kmeans(
        pixels, k, None, criterio, 3, cv2.KMEANS_PP_CENTERS
    )
    rotulos = rotulos.flatten()

    # Reconstrói o mapa de rótulos no formato da máscara.
    mapa = np.full((h, w), -1, np.int32)
    mapa[mascara > 0] = rotulos

    # Remove os agrupamentos que são, na verdade, prato vazio.
    validos: dict[int, float] = {}
    for idx in range(k):
        area = float(np.count_nonzero(rotulos == idx))
        if area <= 0:
            continue
        distancia = float(np.linalg.norm(centros[idx] - cor_prato))
        if distancia < 14:
            continue
        validos[idx] = area

    total_comida = sum(validos.values())
    if total_comida < 0.02 * np.pi * r * r:
        return {"itens": [], "overlay_png": None, "confianca_global": 0.15}

    # Agrupa por categoria (duas cores parecidas podem cair na mesma família).
    somas: dict[str, float] = {}
    for idx, area in validos.items():
        bgr_centro = tuple(int(c) for c in cv2.cvtColor(
            np.uint8([[centros[idx]]]), cv2.COLOR_LAB2BGR
        )[0][0])
        categoria = _classificar_cor(bgr_centro)
        somas[categoria] = somas.get(categoria, 0.0) + area

    itens = [
        {
            "categoria": cat,
            "rotulo": _ROTULO_GENERICO.get(cat, cat),
            "percentual_area": round(area / total_comida, 4),
            "confianca": 0.55,
        }
        for cat, area in sorted(somas.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # Overlay para o painel: pinta cada categoria com sua cor.
    overlay = img.copy()
    for idx in validos:
        bgr_centro = cv2.cvtColor(np.uint8([[centros[idx]]]), cv2.COLOR_LAB2BGR)[0][0]
        categoria = _classificar_cor(tuple(int(c) for c in bgr_centro))
        cor = _hex_para_bgr(CATEGORIAS_PADRAO.get(categoria, {}).get("cor", "#999999"))
        overlay[mapa == idx] = cor
    misturado = cv2.addWeighted(overlay, 0.55, img, 0.45, 0)
    cv2.circle(misturado, (cx, cy), r, (255, 255, 255), 2)
    ok, png = cv2.imencode(".png", misturado)
    overlay_png = png.tobytes() if ok else None

    confianca = float(min(0.75, 0.42 + 0.04 * len(validos)))
    return {"itens": itens, "overlay_png": overlay_png, "confianca_global": confianca}
