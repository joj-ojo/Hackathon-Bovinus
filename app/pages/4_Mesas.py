"""Mesas e cubas: giro do salão e a métrica de reposição que o cliente pediu."""

from __future__ import annotations

import pathlib
import sys

_RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _caminho in (_RAIZ, _RAIZ / "app"):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from ui import garantir_dados, grade_kpis, mesa_card, setup  # noqa: E402

setup("Mesas")

from core import servico  # noqa: E402
from core.db import sessao  # noqa: E402
from core.fluxo import META_LIMPEZA_MIN, cor_mesa  # noqa: E402

garantir_dados()

st.title("Mesas e salão")
st.caption(
    "A câmera detecta que a mesa esvaziou; o garçom confirma a higienização. "
    "O que era 'olhômetro' vira tempo em minutos e prioridade."
)

with sessao() as s:
    mesas = servico.mesas_com_tempo(s)
    ranking = servico.ranking_higienizacao(s, limite=5)
    cubas = servico.reposicoes_do_dia(s)

ocupadas = [m for m in mesas if m["status"] == "ocupada"]
livres = [m for m in mesas if m["status"] == "livre"]
sujas = [m for m in mesas if m["status"] == "suja"]
media_livre = (
    sum(m["minutos_livre"] for m in sujas) / len(sujas) if sujas else 0.0
)

grade_kpis(
    [
        (str(len(ocupadas)), "Ocupadas", "detecção por ROI"),
        (str(len(livres)), "Livres e limpas", "prontas para sentar"),
        (str(len(sujas)), "Aguardando limpeza", f"meta: até {META_LIMPEZA_MIN:.0f} min"),
        (f"{media_livre:.1f} min", "Tempo médio suja", "mesa livre sem higienizar"),
    ]
)

st.divider()

col_esq, col_dir = st.columns([1, 1.25])

with col_esq:
    st.subheader("Prioridade de higienização")
    if not ranking:
        st.success("Nenhuma mesa pendente agora.")
    for mesa in ranking:
        cor = cor_mesa(mesa["minutos_livre"])
        c1, c2 = st.columns([2.4, 1])
        with c1:
            st.markdown(
                f"**Mesa {mesa['id']}** · {mesa['lugares']} lugares · {mesa['nivel']}"
            )
            st.caption(
                f"livre há **{mesa['minutos_livre']:.0f} min** · prioridade {mesa['prioridade']:.0f}"
            )
        with c2:
            if st.button("Higienizada", key=f"hig_{mesa['id']}", use_container_width=True):
                with sessao() as s:
                    servico.mudar_status_mesa(s, mesa["id"], "livre")
                st.rerun()
        st.markdown(
            f"<div style='height:3px;background:{cor};border-radius:2px;margin-bottom:10px'></div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("Simular movimento")
    with sessao() as s:
        mapa = {f"Mesa {m['id']}": m["id"] for m in mesas}
    escolha = st.selectbox("Mesa", list(mapa))
    b1, b2 = st.columns(2)
    if b1.button("Cliente sentou", use_container_width=True):
        with sessao() as s:
            servico.mudar_status_mesa(s, mapa[escolha], "ocupada")
        st.rerun()
    if b2.button("Cliente saiu", use_container_width=True):
        with sessao() as s:
            servico.mudar_status_mesa(s, mapa[escolha], "suja")
        st.rerun()

with col_dir:
    st.subheader("Mapa do salão")
    st.caption("40 mesas visíveis pelas câmeras (o salão tem 90). Cores = status e tempo.")
    for nivel in ("principal", "superior"):
        st.markdown(f"**Salão {nivel}**")
        do_nivel = [m for m in mesas if m["nivel"] == nivel]
        for inicio in range(0, len(do_nivel), 8):
            bloco = do_nivel[inicio : inicio + 8]
            cols = st.columns(8)
            for col, mesa in zip(cols, bloco, strict=False):
                with col:
                    if mesa["status"] == "ocupada":
                        cor = "#6B6259"
                    elif mesa["status"] == "livre":
                        cor = "#3F7D3A"
                    else:
                        cor = cor_mesa(mesa["minutos_livre"])
                    mesa_card(mesa, cor)
        st.write("")

    st.caption(
        "Legenda: verde = livre/limpa · marrom = ocupada · âmbar = suja há mais de 3 min · "
        "vermelho = suja há mais de 6 min."
    )

st.divider()
st.subheader("Cozinha · reposições de cuba")
st.caption(
    "A métrica que a operação disse ser a mais valiosa (\"se o arroz foi reposto cinco vezes, "
    "já é um dado bastante relevante\"). Um toque por reposição."
)

with sessao() as s:
    registros = servico.reposicoes_do_dia(s)

col_a, col_b = st.columns([1.1, 1])
with col_a:
    itens = ["arroz branco", "feijão", "picanha", "costela", "lasanha",
             "salada de grão-de-bico", "farofa", "legumes"]
    item = st.selectbox("Item reposto", itens)
    capacidade = st.number_input("Capacidade da cuba (kg)", 1.0, 30.0, 10.0, step=0.5)
    if st.button("+1 reposição", type="primary", use_container_width=True):
        with sessao() as s:
            servico.registrar_reposicao(s, item, capacidade)
        st.rerun()

with col_b:
    if registros:
        st.dataframe(
            pd.DataFrame(registros)[["item", "reposicoes", "capacidade_kg", "kg_estimado"]].rename(
                columns={
                    "item": "item",
                    "reposicoes": "reposições",
                    "capacidade_kg": "kg/cuba",
                    "kg_estimado": "kg estimado",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
        st.caption("Kg estimado = reposições × capacidade da cuba. É a ponte para o consumo.")
    else:
        st.info("Nenhuma reposição hoje.")
