"""Componentes compartilhados das telas (Streamlit).

Este módulo também é responsável por preparar o ambiente: banco inicializado,
seed sintético e imagens de demonstração.
"""

from __future__ import annotations

import pathlib
import sys

_RAIZ = pathlib.Path(__file__).resolve().parents[1]
for _caminho in (_RAIZ, _RAIZ / "app"):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import streamlit as st  # noqa: E402

CORES = {
    "vinho": "#8B1E2D",
    "carvao": "#2B2523",
    "creme": "#FAF7F2",
    "borda": "#E6DED2",
    "verde": "#3F7D3A",
    "ambar": "#B54708",
    "vermelho": "#B42318",
}

CSS = """
<style>
.stApp { background: #FAF7F2; }
section[data-testid="stSidebar"] { background: #F3EDE3; border-right: 1px solid #E6DED2; }
h1, h2, h3 { color: #2B2523; letter-spacing: -0.02em; }
h1 { font-weight: 800; }
.kpi {
  background: #FFFFFF; border: 1px solid #E6DED2; border-left: 4px solid #8B1E2D;
  border-radius: 10px; padding: 14px 16px; height: 100%;
}
.kpi-valor { font-size: 1.55rem; font-weight: 750; color: #2B2523; line-height: 1.15; }
.kpi-rotulo { font-size: 0.78rem; text-transform: uppercase; letter-spacing: .06em;
  color: #6B6259; margin-top: 4px; }
.kpi-ajuda { font-size: 0.72rem; color: #8A8078; margin-top: 2px; }
.alerta { border-radius: 10px; padding: 11px 14px; margin-bottom: 8px;
  border-left: 4px solid #B54708; background: #FFF8EE; }
.alerta-critica { border-color: #B42318; background: #FDF0EE; }
.alerta-alta { border-color: #B54708; background: #FFF6EA; }
.alerta-media { border-color: #8A6D1F; background: #FFFBE9; }
.alerta-titulo { font-weight: 700; font-size: .86rem; color: #2B2523; }
.alerta-msg { font-size: .82rem; color: #514A44; }
.mesa {
  border-radius: 9px; padding: 9px 6px; text-align: center; color: #fff;
  font-weight: 650; font-size: .78rem; margin-bottom: 6px; line-height: 1.25;
}
.mesa small { display: block; font-weight: 400; opacity: .92; font-size: .68rem; }
.hero {
  background: linear-gradient(120deg, #8B1E2D 0%, #5E1520 100%);
  color: #fff; border-radius: 16px; padding: 26px 28px; margin-bottom: 18px;
}
.hero h2 { color: #fff; margin: 0 0 6px 0; }
.hero p { color: #F3DFD9; margin: 0; font-size: .95rem; }
.tag {
  display: inline-block; background: #EFE6DA; color: #5E4C3C; border-radius: 999px;
  padding: 2px 10px; font-size: .72rem; margin-right: 6px;
}
.rodape { color: #8A8078; font-size: .74rem; margin-top: 26px; }
</style>
"""


def setup(titulo: str, layout: str = "wide") -> None:
    st.set_page_config(
        page_title=f"{titulo} · Bovinu's",
        page_icon="🍖",
        layout=layout,
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner="Preparando dados de demonstração…")
def garantir_dados() -> bool:
    """Inicializa banco, seed sintético e imagens de demo (uma vez por processo)."""
    from core.db import init_db
    from core.demo import gerar_todas
    from core.seed import popular

    init_db()
    popular(force=False)
    gerar_todas()
    return True


def brl(valor: float | None) -> str:
    if valor is None:
        return "—"
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def num(valor: float | int | None, casas: int = 0) -> str:
    if valor is None:
        return "—"
    texto = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto


def pct(valor: float | None, casas: int = 1) -> str:
    return "—" if valor is None else f"{num(valor, casas)}%"


def kpi(valor: str, rotulo: str, ajuda: str = "") -> None:
    st.markdown(
        f'<div class="kpi"><div class="kpi-valor">{valor}</div>'
        f'<div class="kpi-rotulo">{rotulo}</div>'
        f'<div class="kpi-ajuda">{ajuda}</div></div>',
        unsafe_allow_html=True,
    )


def grade_kpis(itens: list[tuple[str, str, str]], colunas: int = 4) -> None:
    for inicio in range(0, len(itens), colunas):
        bloco = itens[inicio : inicio + colunas]
        cols = st.columns(len(bloco))
        for col, (valor, rotulo, ajuda) in zip(cols, bloco, strict=False):
            with col:
                kpi(valor, rotulo, ajuda)


def alerta_card(alerta: dict) -> None:
    st.markdown(
        f'<div class="alerta alerta-{alerta["severidade"]}">'
        f'<div class="alerta-titulo">{alerta["tipo"].replace("_", " ").title()} '
        f'· {alerta["severidade"].upper()}</div>'
        f'<div class="alerta-msg">{alerta["mensagem"]}</div></div>',
        unsafe_allow_html=True,
    )


def mesa_card(mesa: dict, cor: str) -> None:
    st.markdown(
        f'<div class="mesa" style="background:{cor}">'
        f'Mesa {mesa["id"]}<small>{mesa["lugares"]} lugares · {mesa["nivel"]}</small>'
        f'<small>{mesa["status"]}</small></div>',
        unsafe_allow_html=True,
    )


def hero(titulo: str, subtitulo: str) -> None:
    st.markdown(
        f'<div class="hero"><h2>{titulo}</h2><p>{subtitulo}</p></div>',
        unsafe_allow_html=True,
    )


def rodape_dados_sinteticos() -> None:
    st.markdown(
        '<div class="rodape">Dados sintéticos para demonstração, calibrados com os números '
        "informados pela operação (600 clientes/dia, pico 12h10–13h20, R$ 119/kg). "
        "Nenhum dado real de cliente foi usado.</div>",
        unsafe_allow_html=True,
    )


def link_pagina(caminho: str, label: str) -> None:
    """Link interno entre páginas.

    No app normal (multipágina por pasta) o `st.page_link` resolve o caminho.
    Em contextos de teste/preview ele não encontra a página, então caímos para
    um texto simples em vez de quebrar a tela.
    """
    try:
        st.page_link(caminho, label=label)
    except Exception:  # noqa: BLE001 - fallback visual, nunca derrubar a página
        st.caption(f"→ {label}")


def seletor_dia(chave: str = "dia") -> "object":
    from datetime import date, timedelta

    opcoes = [date.today() - timedelta(days=d) for d in (2, 1, 0)]
    rotulos = {d: d.strftime("%d/%m/%Y") + (" (hoje)" if d == date.today() else "") for d in opcoes}
    return st.sidebar.selectbox(
        "Dia de operação",
        options=opcoes,
        index=len(opcoes) - 1,
        format_func=lambda d: rotulos[d],
        key=chave,
    )
