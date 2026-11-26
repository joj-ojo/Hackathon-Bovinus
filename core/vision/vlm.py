"""Cliente do VLM (Gemini ou OpenAI) que devolve a composição do prato em JSON.

Falha de propósito de forma silenciosa: se não houver chave, cota ou internet,
o pipeline cai para a heurística e a demo continua.
"""

from __future__ import annotations

import base64
import json
import logging

from core.config import settings
from core.custos import LISTA_CATEGORIAS

log = logging.getLogger(__name__)

PROMPT = """Você é um nutricionista analisando a foto de um prato de restaurante
self-service brasileiro visto de cima.

Estime a proporção da ÁREA do prato ocupada por cada tipo de alimento visível.
Use exclusivamente estas categorias:
{categorias}

Regras:
- Os percentuais devem somar exatamente 1.0.
- Ignore o prato, talheres, guardanapo e a mesa.
- Se houver molho sobre a carne, considere a carne.
- Se um alimento não se encaixar em nenhuma categoria, use "outros".
- Use no máximo 5 itens, do maior para o menor.
- "rotulo" é o nome do alimento em português, curto (ex.: "picanha", "arroz branco").

Responda SOMENTE com JSON válido neste formato:
{{"itens":[{{"categoria":"carne_premium","rotulo":"picanha","percentual_area":0.22}}],"confianca":0.8}}

"confianca" é sua confiança global de 0 a 1."""


def disponivel() -> bool:
    return bool(settings.gemini_api_key or settings.openai_api_key)


def _prompt() -> str:
    return PROMPT.format(categorias="\n".join(f"- {c}" for c in LISTA_CATEGORIAS))


def _limpar_json(texto: str) -> dict | None:
    texto = (texto or "").strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.lstrip().startswith("json"):
            texto = texto.lstrip()[4:]
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fim < 0:
        return None
    try:
        return json.loads(texto[inicio : fim + 1])
    except json.JSONDecodeError:
        return None


def _via_gemini(foto_bytes: bytes) -> dict | None:
    if not settings.gemini_api_key:
        return None
    try:
        from google import genai
        from google.genai import types

        cliente = genai.Client(api_key=settings.gemini_api_key)
        resposta = cliente.models.generate_content(
            model=settings.gemini_model,
            contents=[
                _prompt(),
                types.Part.from_bytes(data=foto_bytes, mime_type="image/jpeg"),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        return _limpar_json(resposta.text)
    except Exception as exc:  # noqa: BLE001 - qualquer falha cai para o próximo método
        log.warning("Gemini indisponível: %s", exc)
        return None


def _via_openai(foto_bytes: bytes) -> dict | None:
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        cliente = OpenAI(api_key=settings.openai_api_key)
        b64 = base64.b64encode(foto_bytes).decode()
        resposta = cliente.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _prompt()},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
        )
        return _limpar_json(resposta.choices[0].message.content or "")
    except Exception as exc:  # noqa: BLE001
        log.warning("OpenAI indisponível: %s", exc)
        return None


def analisar(foto_bytes: bytes, provider: str = "auto") -> dict | None:
    """Tenta o VLM configurado. Retorna None se nada estiver disponível."""
    provedor = provider if provider != "auto" else (
        "gemini" if settings.gemini_api_key else ("openai" if settings.openai_api_key else "")
    )
    if provedor == "gemini":
        return _via_gemini(foto_bytes)
    if provedor == "openai":
        return _via_openai(foto_bytes)
    return None
