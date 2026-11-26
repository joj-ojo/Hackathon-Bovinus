"""Demonstração ponta a ponta: comanda → prato → CMV → feedback."""

from __future__ import annotations

import pathlib
import sys

_RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _caminho in (_RAIZ, _RAIZ / "app"):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from ui import (  # noqa: E402
    brl,
    garantir_dados,
    grade_kpis,
    link_pagina,
    pct,
    rodape_dados_sinteticos,
    seletor_dia,
    setup,
)

setup("Comandas")

from core import servico  # noqa: E402
from core.config import RAIZ  # noqa: E402
from core.db import sessao  # noqa: E402

garantir_dados()

st.title("Comandas · a demonstração ponta a ponta")
st.caption(
    "O número da comanda é a chave única. Abertura → pesagem com foto → bebida → feedback → fechamento."
)

dia = seletor_dia("dia_comandas")

with sessao() as s:
    lista = servico.listar_comandas(s, dia, limite=250)
    ind = servico.indicadores(s, dia)
    proxima = servico.proximo_numero(s)

grade_kpis(
    [
        (str(ind["comandas"]), "Comandas no dia", f"{ind['comandas_abertas']} abertas"),
        (brl(ind["receita_total"]), "Receita", "prato + bebida"),
        (pct(ind["cmv_pct"]), "CMV médio", "prato"),
        (brl(ind["ticket_medio"]), "Ticket médio", "por comanda"),
    ]
)

st.divider()

col_esq, col_dir = st.columns([1.6, 1])

with col_esq:
    st.subheader("Comandas do dia")
    if lista:
        df = pd.DataFrame(lista)
        st.dataframe(
            df.rename(
                columns={
                    "comanda": "comanda",
                    "hora": "hora",
                    "pessoas": "pessoas",
                    "pratos": "pratos",
                    "peso_g": "peso (g)",
                    "receita": "receita (R$)",
                    "cmv_pct": "CMV (%)",
                    "nota": "nota",
                    "status": "status",
                }
            ),
            hide_index=True,
            use_container_width=True,
            height=420,
        )
    else:
        st.info("Nenhuma comanda neste dia.")

with col_dir:
    st.subheader("Abrir uma comanda")
    opcoes = [c["comanda"] for c in lista]
    if opcoes:
        numero = st.selectbox(
            "Número", opcoes, format_func=lambda n: f"{n} · {next(c['hora'] for c in lista if c['comanda'] == n)}"
        )
    else:
        numero = st.text_input("Número", value=proxima)

    if st.button("Nova comanda (simular abertura)", use_container_width=True):
        with sessao() as s:
            nova = servico.criar_comanda(s)
        st.success(f"Comanda {nova} aberta na recepção humanizada.")
        link_pagina("pages/1_Balanca.py", label="Pesar o prato desta comanda →")
        st.stop()

with sessao() as s:
    resumo = servico.resumo_comanda(s, numero) if numero else None

if not resumo:
    st.warning("Comanda não encontrada.")
    st.stop()

st.divider()
st.markdown(f"## Comanda {resumo['numero']}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Pessoas", resumo["pessoas"])
c2.metric("Aberta", resumo["aberta_em"].strftime("%H:%M"))
c3.metric("Bebidas", brl(resumo["bebidas"]))
c4.metric("Status", "fechada" if resumo["fechada_em"] else "aberta")

grade_kpis(
    [
        (brl(resumo["totais"]["receita"]), "Receita da comanda", "prato + bebida"),
        (brl(resumo["totais"]["custo"]), "Custo estimado", "tabela de custo/kg"),
        (brl(resumo["totais"]["margem"]), "Margem", "receita − custo"),
        (pct(resumo["totais"]["cmv_pct"]), "CMV da comanda", "inclui bebida a 30%"),
    ]
)

if not resumo["pratos"]:
    st.info("Esta comanda ainda não tem prato pesado. Vá em **Balança** para registrar.")

for prato in resumo["pratos"]:
    with st.expander(
        f"Prato das {prato['hora']} · {prato['peso_g']} g · CMV {prato['cmv_pct']:.1f}%",
        expanded=True,
    ):
        esq, dir_ = st.columns([1, 1.2])
        with esq:
            caminho = RAIZ / prato["foto_path"] if prato["foto_path"] else None
            if caminho and caminho.exists():
                st.image(str(caminho), caption="Foto da balança", use_container_width=True)
            else:
                st.info("Foto não disponível (dados sintéticos do dia).")
            st.caption(f"Modelo: `{prato['modelo']}`")
        with dir_:
            grade_kpis(
                [
                    (brl(prato["receita"]), "Receita", f"{prato['peso_g']} g"),
                    (brl(prato["custo"]), "Custo", "composição estimada"),
                    (brl(prato["margem"]), "Margem", "bruta"),
                    (pct(prato["mix_premium_pct"]), "Mix premium", "área do prato"),
                ]
            )
            st.dataframe(
                pd.DataFrame(prato["itens"]).assign(
                    percentual=lambda d: (d["percentual"] * 100)
                )[["rotulo", "categoria", "percentual", "peso_g", "custo"]].rename(
                    columns={
                        "rotulo": "item",
                        "categoria": "categoria",
                        "percentual": "área (%)",
                        "peso_g": "peso (g)",
                        "custo": "custo (R$)",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )

st.divider()
col_fb, col_vazio = st.columns([1.4, 1])
with col_fb:
    st.subheader("Feedback vinculado")
    if resumo["feedbacks"]:
        st.dataframe(pd.DataFrame(resumo["feedbacks"]), hide_index=True, use_container_width=True)
        link_pagina("pages/2_Feedback.py", label="Abrir o totem de feedback →")
    else:
        st.info("Sem avaliação ainda. O totem/QR grava direto nesta comanda.")
        link_pagina("pages/2_Feedback.py", label="Abrir o totem de feedback →")

with col_vazio:
    st.subheader("Por que isso importa")
    st.markdown(
        """
- A comanda liga **quanto o cliente pagou** a **o que ele comeu**.
- Com o feedback, a comanda também liga **o que ele achou**.
- É o único lugar do sistema em que mix, CMV, margem e satisfação aparecem juntos.
        """
    )

rodape_dados_sinteticos()
