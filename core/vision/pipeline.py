"""Pipeline de análise do prato: VLM -> heurística -> manual, com cache e persistência."""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import time
import uuid
from datetime import datetime

from core.config import FOTOS_DIR, RAIZ, settings
from core.cmv import calcular_cmv
from core.custos import dicionario_categorias

log = logging.getLogger(__name__)

_CACHE: dict[str, dict] = {}
_CACHE_MAX = 40


def salvar_foto(foto_bytes: bytes) -> str:
    """Grava a foto em disco (WebP, 640px) e devolve o caminho relativo à raiz."""
    try:
        from PIL import Image

        imagem = Image.open(io.BytesIO(foto_bytes)).convert("RGB")
        imagem.thumbnail((640, 640))
        nome = f"{uuid.uuid4().hex[:12]}.webp"
        destino = FOTOS_DIR / nome
        imagem.save(destino, format="WEBP", quality=78)
        return destino.relative_to(RAIZ).as_posix()
    except Exception as exc:  # noqa: BLE001
        log.warning("Não foi possível gravar a foto: %s", exc)
        return ""


def _chave(foto_bytes: bytes, peso_g: float, provider: str) -> str:
    digest = hashlib.sha1(foto_bytes).hexdigest()[:16]
    return f"{digest}:{int(peso_g)}:{provider}"


def analisar_bytes(
    foto_bytes: bytes,
    peso_g: float,
    preco_kg: float | None = None,
    categorias_db=None,
    provider: str | None = None,
) -> dict:
    """Analisa a foto e devolve o contrato JSON completo (itens + CMV + metadados)."""
    from core.vision import heuristica, vlm

    preco = preco_kg or settings.preco_kg
    categorias = dicionario_categorias(categorias_db)
    provedor = (provider or settings.vision_provider or "auto").lower()

    chave = _chave(foto_bytes, peso_g, provedor)
    if chave in _CACHE:
        return _CACHE[chave]

    inicio = time.perf_counter()
    dados = vlm.analisar(foto_bytes, provedor) if provedor != "heuristica" else None
    modelo = "vlm"
    overlay = None

    if dados and dados.get("itens"):
        modelo = f"vlm:{settings.gemini_model if settings.gemini_api_key else settings.openai_model}"
        confianca = float(dados.get("confianca", 0.7) or 0.7)
    else:
        heuristico = heuristica.analisar(foto_bytes) if provedor != "gemini" else {"itens": []}
        dados = heuristico
        modelo = "heuristica:opencv"
        overlay = heuristico.get("overlay_png")
        confianca = float(heuristico.get("confianca_global", 0.0) or 0.0)

    itens = dados.get("itens") or []
    itens = [i for i in itens if i.get("categoria") in categorias]
    resultado = calcular_cmv(peso_g, itens, preco, categorias)

    status = "ok"
    if not itens:
        status = "manual"
    elif confianca < 0.55:
        status = "revisar"

    saida = {
        "prato_id": uuid.uuid4().hex[:12],
        "peso_total_g": int(peso_g),
        "confianca_global": round(confianca, 3),
        "modelo": modelo,
        "status": status,
        "latencia_ms": int((time.perf_counter() - inicio) * 1000),
        "provider": provedor,
        "overlay_png_b64": base64.b64encode(overlay).decode() if overlay else None,
        **resultado.como_dict(),
    }

    if len(_CACHE) > _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[chave] = saida
    return saida


def analisar_manual(
    composicao: dict[str, float],
    peso_g: float,
    preco_kg: float | None = None,
    categorias_db=None,
) -> dict:
    """Fallback humano: o operador informa as proporções em 3 chips."""
    categorias = dicionario_categorias(categorias_db)
    itens = [
        {"categoria": cat, "rotulo": "", "percentual_area": pct, "confianca": 1.0}
        for cat, pct in composicao.items()
        if pct > 0
    ]
    resultado = calcular_cmv(peso_g, itens, preco_kg or settings.preco_kg, categorias)
    return {
        "prato_id": uuid.uuid4().hex[:12],
        "peso_total_g": int(peso_g),
        "confianca_global": 1.0,
        "modelo": "manual",
        "status": "ok",
        "latencia_ms": 0,
        "provider": "manual",
        "overlay_png_b64": None,
        **resultado.como_dict(),
    }


def persistir_pesagem(
    session,
    comanda_numero: str,
    resultado: dict,
    foto_path: str = "",
    balanca_id: str = "B1",
    quando: datetime | None = None,
) -> str:
    """Grava a pesagem e seus itens. Exige que a comanda já exista."""
    from core.models import Pesagem, PesagemItem

    pesagem = Pesagem(
        id=resultado.get("prato_id") or uuid.uuid4().hex[:12],
        comanda_numero=comanda_numero,
        balanca_id=balanca_id,
        peso_g=resultado["peso_total_g"],
        preco_kg=settings.preco_kg,
        foto_path=foto_path or None,
        modelo=resultado.get("modelo", "heuristica"),
        confianca=resultado.get("confianca_global", 0.0),
        custo_estimado=resultado["cmv"]["custo_total"],
        receita_prato=resultado["cmv"]["receita"],
        cmv_pct=resultado["cmv"]["cmv_pct"],
        criado_em=quando or datetime.now(),
    )
    for item in resultado.get("itens", []):
        pesagem.itens.append(
            PesagemItem(
                categoria=item["categoria"],
                rotulo=item.get("rotulo") or "",
                percentual_area=item["percentual_area"],
                peso_estimado_g=item["peso_estimado_g"],
                custo_kg=item["custo_kg"],
                custo=item["custo"],
                confianca=item.get("confianca", 0.0),
            )
        )
    session.add(pesagem)
    session.flush()
    return pesagem.id
