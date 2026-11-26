"""Entrada do app Streamlit: visão geral do sistema."""

from __future__ import annotations

import pathlib
import sys

_RAIZ = pathlib.Path(__file__).resolve().parents[1]
for _caminho in (_RAIZ, _RAIZ / "app"):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import streamlit as st  # noqa: E402

from ui import brl, garantir_dados, grade_kpis, hero, pct, rodape_dados_sinteticos, setup  # noqa: E402

setup("Visão geral")

from core import servico  # noqa: E402
from core.db import sessao  # noqa: E402

garantir_dados()

hero(
    "Inteligência Operacional · Bovinu's Grill & Beer",
    "A camada que transforma o que a operação vê em número: mix do prato, CMV, filas, "
    "mesas e satisfação — tudo ligado pelo número da comanda.",
)

with sessao() as s:
    ind = servico.indicadores(s)
    alertas = servico.alertas_atuais(s)

grade_kpis(
    [
        (str(ind["comandas"]), "Comandas hoje", f"{ind['comandas_abertas']} ainda abertas"),
        (pct(ind["cmv_pct"]), "CMV médio", "custo do prato / receita do prato"),
        (brl(ind["margem"]), "Margem estimada", "prato + bebida, custo estimado"),
        (brl(ind["ticket_medio"]), "Ticket médio", "por comanda"),
        (pct(ind["mix_premium_pct"]), "Mix premium", "% da área do prato em carne premium"),
        (f"{ind['csat']:.1f}/4", "Satisfação", f"{ind['feedbacks']} feedbacks"),
        (f"{ind['espera_p95_min']:.1f} min", "Espera p95", "churrasqueira (meta 2,5)"),
        (f"{ind['mesa_suja_p95_min']:.0f} min", "Mesa suja p95", f"{ind['mesas_sujas']} aguardando"),
    ],
    colunas=4,
)

st.divider()

esquerda, direita = st.columns([1.35, 1])

with esquerda:
    st.subheader("As quatro dores, resolvidas na mesma chave")
    st.markdown(
        """
| Dor | Métrica que passa a existir | Onde aparece |
|---|---|---|
| **1 · Mix do prato e CMV** | % de cada categoria no prato, custo/kg, CMV e margem por comanda | Balança → Painel |
| **2 · Filas e tempo** | espera estimada por estação, fila na escada, p95 | Painel |
| **3 · Limpeza e giro** | minutos de mesa livre até higienizar, prioridade | Mesas |
| **4 · Qualidade e desperdício** | nota por item, resto, reposições de cuba | Feedback → Painel |
        """
    )
    st.markdown(
        '<span class="tag">não invasivo</span>'
        '<span class="tag">comanda como chave única</span>'
        '<span class="tag">reuso das câmeras Intelbras</span>'
        '<span class="tag">recepção humanizada preservada</span>',
        unsafe_allow_html=True,
    )

with direita:
    st.subheader("Alertas ativos")
    if not alertas:
        st.success("Nenhum alerta agora. Operação dentro da meta.")
    for alerta in alertas[:5]:
        st.markdown(
            f'<div class="alerta alerta-{alerta["severidade"]}">'
            f'<div class="alerta-titulo">{alerta["tipo"].replace("_", " ").title()}</div>'
            f'<div class="alerta-msg">{alerta["mensagem"]}</div></div>',
            unsafe_allow_html=True,
        )

st.divider()
st.subheader("Comece por aqui")
colunas = st.columns(4)
atalhos = [
    ("Balança", "Foto do prato → composição → CMV", "pages/1_Balanca.py"),
    ("Feedback", "Totem 1-clique + Pergunta do Dia", "pages/2_Feedback.py"),
    ("Painel", "Mix × satisfação, filas e margem", "pages/3_Painel.py"),
    ("Mesas", "Prioridade de higienização em tempo real", "pages/4_Mesas.py"),
]
for col, (titulo, texto, _) in zip(colunas, atalhos, strict=False):
    with col:
        st.markdown(f"**{titulo}**")
        st.caption(texto)
st.caption("Use o menu lateral para navegar. A página **Comandas** faz a demonstração ponta a ponta.")

rodape_dados_sinteticos()
