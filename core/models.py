"""Modelo de dados. A chave única de rastreamento é sempre o número da comanda."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Comanda(Base):
    __tablename__ = "comandas"

    numero: Mapped[str] = mapped_column(String(8), primary_key=True)
    codigo_barras: Mapped[str | None] = mapped_column(String(64), nullable=True)
    origem: Mapped[str] = mapped_column(String(16), default="simulado")
    aberta_em: Mapped[datetime] = mapped_column(default=datetime.now)
    fechada_em: Mapped[datetime | None] = mapped_column(nullable=True)
    pessoas: Mapped[int] = mapped_column(Integer, default=1)
    bebidas_valor: Mapped[float] = mapped_column(default=0.0)
    valor_pago: Mapped[float | None] = mapped_column(nullable=True)

    pesagens: Mapped[list["Pesagem"]] = relationship(
        back_populates="comanda", cascade="all, delete-orphan"
    )
    feedbacks: Mapped[list["Feedback"]] = relationship(
        back_populates="comanda", cascade="all, delete-orphan"
    )


class Pesagem(Base):
    __tablename__ = "pesagens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    comanda_numero: Mapped[str] = mapped_column(ForeignKey("comandas.numero"), index=True)
    balanca_id: Mapped[str] = mapped_column(String(16), default="B1")
    peso_g: Mapped[int] = mapped_column(Integer)
    preco_kg: Mapped[float] = mapped_column(default=119.0)
    foto_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    modelo: Mapped[str] = mapped_column(String(40), default="heuristica")
    confianca: Mapped[float] = mapped_column(default=0.0)
    custo_estimado: Mapped[float] = mapped_column(default=0.0)
    receita_prato: Mapped[float] = mapped_column(default=0.0)
    cmv_pct: Mapped[float] = mapped_column(default=0.0)
    criado_em: Mapped[datetime] = mapped_column(default=datetime.now, index=True)

    comanda: Mapped["Comanda"] = relationship(back_populates="pesagens")
    itens: Mapped[list["PesagemItem"]] = relationship(
        back_populates="pesagem", cascade="all, delete-orphan"
    )

    @property
    def mix_premium(self) -> float:
        """Fração da área do prato ocupada por carne premium (0 a 1)."""
        return sum(i.percentual_area for i in self.itens if i.categoria == "carne_premium")



class PesagemItem(Base):
    __tablename__ = "pesagem_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pesagem_id: Mapped[str] = mapped_column(ForeignKey("pesagens.id"), index=True)
    categoria: Mapped[str] = mapped_column(String(32))
    rotulo: Mapped[str] = mapped_column(String(64), default="")
    percentual_area: Mapped[float] = mapped_column(default=0.0)
    peso_estimado_g: Mapped[int] = mapped_column(Integer, default=0)
    custo_kg: Mapped[float] = mapped_column(default=0.0)
    custo: Mapped[float] = mapped_column(default=0.0)
    confianca: Mapped[float] = mapped_column(default=0.0)

    pesagem: Mapped["Pesagem"] = relationship(back_populates="itens")


class CategoriaCusto(Base):
    __tablename__ = "categorias_custo"

    categoria: Mapped[str] = mapped_column(String(32), primary_key=True)
    rotulo: Mapped[str] = mapped_column(String(64))
    custo_kg: Mapped[float] = mapped_column(default=0.0)
    densidade: Mapped[float] = mapped_column(default=1.0)  # g/cm² de superfície
    cor: Mapped[str] = mapped_column(String(9), default="#cccccc")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comanda_numero: Mapped[str] = mapped_column(ForeignKey("comandas.numero"), index=True)
    nota_geral: Mapped[int] = mapped_column(Integer, default=0)
    item_perguntado: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nota_item: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resto: Mapped[str | None] = mapped_column(String(16), nullable=True)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    canal: Mapped[str] = mapped_column(String(16), default="totem")
    criado_em: Mapped[datetime] = mapped_column(default=datetime.now, index=True)

    comanda: Mapped["Comanda"] = relationship(back_populates="feedbacks")


class Mesa(Base):
    __tablename__ = "mesas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nivel: Mapped[str] = mapped_column(String(16), default="principal")
    lugares: Mapped[int] = mapped_column(Integer, default=4)
    status: Mapped[str] = mapped_column(String(16), default="livre")
    ocupada_desde: Mapped[datetime | None] = mapped_column(nullable=True)
    livre_desde: Mapped[datetime | None] = mapped_column(nullable=True)
    higienizada_em: Mapped[datetime | None] = mapped_column(nullable=True)


class EventoFila(Base):
    __tablename__ = "eventos_fila"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zona: Mapped[str] = mapped_column(String(24), index=True)  # entrada|churrasqueira|caixa
    pessoas: Mapped[int] = mapped_column(Integer, default=0)
    chegadas_por_min: Mapped[float] = mapped_column(default=0.0)
    espera_estimada_min: Mapped[float] = mapped_column(default=0.0)
    criado_em: Mapped[datetime] = mapped_column(default=datetime.now, index=True)


class ReposicaoCuba(Base):
    __tablename__ = "reposicoes_cuba"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item: Mapped[str] = mapped_column(String(64))
    capacidade_kg: Mapped[float] = mapped_column(default=10.0)
    operador: Mapped[str] = mapped_column(String(32), default="cozinha")
    criado_em: Mapped[datetime] = mapped_column(default=datetime.now, index=True)


class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(32))
    severidade: Mapped[str] = mapped_column(String(16), default="media")
    entidade: Mapped[str] = mapped_column(String(64), default="")
    mensagem: Mapped[str] = mapped_column(Text, default="")
    criado_em: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
    resolvido_em: Mapped[datetime | None] = mapped_column(nullable=True)
