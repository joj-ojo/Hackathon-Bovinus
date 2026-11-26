"""Sessão e inicialização do banco. SQLite no demo, Postgres/Supabase em produção."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings
from core.custos import CATEGORIAS_PADRAO
from core.models import Base, CategoriaCusto

_url = settings.database_url
_conecta_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}

engine = create_engine(_url, connect_args=_conecta_args, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


@event.listens_for(engine, "connect")
def _pragmas(dbapi_conn, _rec):  # pragma: no cover - infraestrutura
    if _url.startswith("sqlite"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


def init_db() -> None:
    """Cria as tabelas e garante a tabela de custos (idempotente)."""
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        existentes = {c.categoria for c in s.scalars(select(CategoriaCusto))}
        for chave, dados in CATEGORIAS_PADRAO.items():
            if chave not in existentes:
                s.add(CategoriaCusto(categoria=chave, **dados))
        s.commit()


@contextmanager
def sessao() -> Iterator[Session]:
    """Context manager de sessão: commit no sucesso, rollback no erro."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
