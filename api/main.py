"""API FastAPI: a mesma inteligência do painel, exposta para integração.

Rodar: uvicorn api.main:app --reload --port 8000
Docs:  http://localhost:8000/docs
"""

from __future__ import annotations

import pathlib
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime

_RAIZ = pathlib.Path(__file__).resolve().parents[1]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from sqlalchemy import select  # noqa: E402

from core import servico  # noqa: E402
from core.db import init_db, sessao  # noqa: E402
from core.models import CategoriaCusto, Comanda, EventoFila  # noqa: E402
from core.seed import popular  # noqa: E402
from core.vision import analisar_bytes, persistir_pesagem, salvar_foto  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    popular(force=False)
    yield


app = FastAPI(
    title="Bovinu's · Inteligência Operacional",
    description=(
        "Camada PaaS não invasiva sobre o sistema de comandas. "
        "A chave única de rastreamento é o número da comanda."
    ),
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class FeedbackIn(BaseModel):
    comanda: str = Field(..., examples=["0421"])
    nota_geral: int = Field(..., ge=1, le=4)
    item: str | None = None
    nota_item: int | None = Field(default=None, ge=1, le=4)
    resto: str | None = Field(default=None, pattern="^(nada|pouco|muito)$")
    comentario: str | None = None
    canal: str = "totem"


class ComandaIn(BaseModel):
    numero: str | None = None
    pessoas: int = Field(default=2, ge=1, le=30)


class EventoComanda(BaseModel):
    evento: str = Field(..., examples=["comanda.aberta", "item.lancado", "comanda.fechada"])
    comanda: str
    timestamp: datetime | None = None
    payload: dict | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "servico": "bovinus-inteligencia", "versao": "0.1.0"}


@app.get("/api/v1/indicadores")
def indicadores(dia: date | None = None) -> dict:
    with sessao() as s:
        dados = servico.indicadores(s, dia)
    dados["dia"] = dados["dia"].isoformat()
    return dados


@app.get("/api/v1/categorias")
def categorias() -> list[dict]:
    with sessao() as s:
        return [
            {
                "categoria": c.categoria,
                "rotulo": c.rotulo,
                "custo_kg": c.custo_kg,
                "densidade": c.densidade,
            }
            for c in s.scalars(select(CategoriaCusto))
        ]


@app.post("/api/v1/pratos/analisar")
async def analisar_prato(
    foto: UploadFile = File(...),
    comanda: str = Form(...),
    peso_g: float = Form(...),
    persistir: bool = Form(default=False),
    balanca_id: str = Form(default="B1"),
) -> dict:
    """Analisa a foto do prato e devolve composição + CMV.

    Com `persistir=true`, grava a pesagem na comanda (cria a comanda se não existir).
    """
    conteudo = await foto.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo de foto vazio.")
    if peso_g <= 0:
        raise HTTPException(status_code=400, detail="Peso deve ser maior que zero.")

    resultado = analisar_bytes(conteudo, peso_g)

    if persistir:
        with sessao() as s:
            servico.criar_comanda(s, numero=comanda)
            caminho = salvar_foto(conteudo)
            persistir_pesagem(s, comanda, resultado, foto_path=caminho, balanca_id=balanca_id)
        resultado["persistido"] = True

    return resultado


@app.post("/api/v1/feedback", status_code=201)
def criar_feedback(dados: FeedbackIn) -> dict:
    with sessao() as s:
        servico.criar_comanda(s, numero=dados.comanda)
        servico.registrar_feedback(
            s,
            comanda_numero=dados.comanda,
            nota_geral=dados.nota_geral,
            item=dados.item,
            nota_item=dados.nota_item,
            resto=dados.resto,
            comentario=dados.comentario,
            canal=dados.canal,
        )
    return {"ok": True, "comanda": dados.comanda}


@app.post("/api/v1/comandas", status_code=201)
def abrir_comanda(dados: ComandaIn) -> dict:
    with sessao() as s:
        numero = servico.criar_comanda(s, numero=dados.numero, pessoas=dados.pessoas)
    return {"comanda": numero, "aberta_em": datetime.now().isoformat()}


@app.get("/api/v1/comandas/{numero}")
def obter_comanda(numero: str) -> dict:
    with sessao() as s:
        resumo = servico.resumo_comanda(s, numero)
    if not resumo:
        raise HTTPException(status_code=404, detail="Comanda não encontrada.")
    resumo["aberta_em"] = resumo["aberta_em"].isoformat()
    resumo["fechada_em"] = resumo["fechada_em"].isoformat() if resumo["fechada_em"] else None
    return resumo


@app.get("/api/v1/alertas")
def alertas(dia: date | None = None) -> list[dict]:
    with sessao() as s:
        return servico.alertas_atuais(s, dia)


@app.get("/api/v1/fila")
def fila(dia: date | None = None) -> list[dict]:
    with sessao() as s:
        atual = servico.fila_atual(s, dia)
    return [{**e, "hora": e["hora"].isoformat()} for e in atual]


@app.post("/webhooks/comanda", status_code=202)
def webhook_comanda(evento: EventoComanda) -> dict:
    """Contrato sugerido para quando o JS Softcom expuser eventos.

    Hoje o MVP não depende disto: ele captura o dado na balança. Este endpoint
    existe para mostrar o caminho de integração ideal (opção C do documento).
    """
    if evento.evento not in {"comanda.aberta", "item.lancado", "comanda.fechada"}:
        raise HTTPException(status_code=422, detail="Evento não suportado.")

    with sessao() as s:
        comanda = s.get(Comanda, evento.comanda)
        if evento.evento == "comanda.aberta":
            servico.criar_comanda(s, numero=evento.comanda)
        elif evento.evento == "item.lancado" and comanda and evento.payload:
            valor = float(evento.payload.get("valor", 0))
            if evento.payload.get("tipo") == "bebida":
                comanda.bebidas_valor += valor
        elif evento.evento == "comanda.fechada" and comanda:
            comanda.fechada_em = evento.timestamp or datetime.now()
            if evento.payload:
                comanda.valor_pago = float(evento.payload.get("valor_pago", 0)) or comanda.valor_pago

    return {"recebido": True, "evento": evento.evento, "comanda": evento.comanda}


@app.get("/api/v1/eventos-fila")
def eventos_fila(dia: date | None = None) -> list[dict]:
    with sessao() as s:
        eventos = servico.fila_do_dia(s, dia)
    return [
        {**e, "hora": e["hora"].isoformat()} if isinstance(e["hora"], (datetime,)) else e
        for e in eventos
    ]
