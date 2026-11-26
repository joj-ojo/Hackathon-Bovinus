"""Painel gerencial: o cruzamento que hoje não existe."""

from __future__ import annotations

import pathlib
import sys

_RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _caminho in (_RAIZ, _RAIZ / "app"):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from sqlalchemy import select  # noqa: E402

from ui import brl, garantir_dados, grade_kpis, pct, rodape_dados_sinteticos, seletor_dia, setup  # noqa: E402

setup("Painel")

from core import servico  # noqa: E402
from core.custos import CATEGORIAS_PADRAO  # noqa: E402
from core.db import sessao  # noqa: E402
from core.models import CategoriaCusto  # noqa: E402

garantir_dados()

VINHO = "#8B1E2D"
AMBAR = "#B54708"
VERDE = "#3F7D3A"

dia = seletor_dia()

with sessao() as s:
    ind = servico.indicadores(s, dia)
    pontos = servico.mix_satisfacao(s, dia)
    por_hora = servico.cmv_por_hora(s, dia)
    ranking = servico.ranking_itens(s, dias=3)
    cubas = servico.reposicoes_do_dia(s, dia)
    fila = servico.fila_do_dia(s, dia)
    sujas = servico.ranking_higienizacao(s, limite=6)
    alertas = servico.alertas_atuais(s, dia)

st.markdown(f"## Painel · {dia.strftime('%d/%m/%Y')}")
st.caption(
    "Dados sintéticos calibrados com a operação real. O objetivo é provar o cruzamento, "
    "não prever o faturamento."
)

grade_kpis(
    [
        (str(ind["comandas"]), "Comandas", f"{ind['comandas_abertas']} abertas"),
        (pct(ind["cmv_pct"]), "CMV médio", "prato, sem bebida"),
        (brl(ind["margem"]), "Margem do dia", "prato + bebida"),
        (brl(ind["ticket_medio"]), "Ticket médio", "por comanda"),
        (pct(ind["mix_premium_pct"]), "Mix premium", "área do prato"),
        (f"{ind['csat']:.2f}/4", "Satisfação", f"{ind['feedbacks']} respostas"),
        (pct(ind["taxa_feedback_pct"]), "Taxa de resposta", "do total de comandas"),
        (f"{ind['espera_p95_min']:.1f} min", "Espera p95", "churrasqueira"),
    ]
)

st.divider()

col_esq, col_dir = st.columns(2)

with col_esq:
    st.subheader("CMV ao longo do serviço")
    if por_hora:
        df = pd.DataFrame(por_hora)
        fig = px.bar(df, x="hora", y="cmv_pct", text="pratos", color_discrete_sequence=[VINHO])
        fig.add_hrect(y0=28, y1=32, fillcolor=VERDE, opacity=0.12, line_width=0)
        fig.update_traces(texttemplate="%{text} pratos", textposition="outside")
        fig.update_layout(
            height=320, yaxis_title="CMV (%)", xaxis_title="", showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Faixa verde: 28–32%, referência de food cost para self-service.")
    else:
        st.info("Sem pesagens neste dia.")

with col_dir:
    st.subheader("Mix premium por hora")
    if por_hora:
        df = pd.DataFrame(por_hora)
        fig = px.area(df, x="hora", y="mix_premium_pct", color_discrete_sequence=[AMBAR])
        fig.update_layout(
            height=320, yaxis_title="% da área do prato", xaxis_title="",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Quando o mix premium sobe, o CMV sobe junto — e a margem cai.")

st.divider()

col_a, col_b = st.columns([1.2, 1])

with col_a:
    st.subheader("Mix × satisfação, por comanda")
    if pontos:
        df = pd.DataFrame(pontos)
        fig = px.scatter(
            df,
            x="mix_premium_pct",
            y="nota",
            size="peso_g",
            color="cmv_pct",
            color_continuous_scale=["#E8D5A8", "#B54708", "#8B1E2D"],
            hover_data=["comanda", "peso_g"],
            labels={
                "mix_premium_pct": "Mix premium (%)",
                "nota": "Nota (1–4)",
                "cmv_pct": "CMV (%)",
            },
        )
        fig.update_yaxes(dtick=1, range=[0.5, 4.5])
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Cada ponto é uma comanda com feedback e prato fotografado. "
            "É a pergunta que a operação nunca conseguiu responder: prato caro deixa o cliente mais feliz?"
        )
    else:
        st.info("Ainda não há comandas com prato + feedback neste dia.")

with col_b:
    st.subheader("Itens com pior aceitação")
    if ranking:
        df = pd.DataFrame(ranking[:8])
        fig = px.bar(
            df,
            x="nota_media",
            y="item",
            orientation="h",
            text="avaliacoes",
            color="nota_media",
            color_continuous_scale=["#B42318", "#B54708", "#3F7D3A"],
            range_color=[1, 4],
        )
        fig.update_traces(texttemplate="%{text} aval.", textposition="outside")
        fig.update_layout(
            height=360, xaxis_title="Nota média (1–4)", yaxis_title="",
            coloraxis_showscale=False, margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem feedback de item ainda.")

st.divider()

col_c, col_d = st.columns(2)

with col_c:
    st.subheader("Fila por estação")
    if fila:
        df = pd.DataFrame(fila)
        df["hora"] = pd.to_datetime(df["hora"])
        fig = px.line(
            df,
            x="hora",
            y="espera_min",
            color="zona",
            color_discrete_map={
                "entrada": "#8B1E2D",
                "churrasqueira": "#B54708",
                "caixa": "#3F7D3A",
            },
            labels={"espera_min": "Espera estimada (min)", "hora": "", "zona": "Zona"},
        )
        fig.add_hline(
            y=2.5, line_dash="dot", line_color="#2B2523",
            annotation_text="meta churrasqueira 2,5 min", annotation_position="top left",
        )
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Espera calculada pela Lei de Little (pessoas ÷ chegadas por minuto). "
            "A linha da entrada é o risco de o cliente ver a fila na escada e ir embora."
        )
    else:
        st.info("Sem eventos de fila.")

with col_d:
    st.subheader("Reposições de cuba")
    if cubas:
        df = pd.DataFrame(cubas)
        fig = px.bar(
            df,
            x="reposicoes",
            y="item",
            orientation="h",
            text="reposicoes",
            color="reposicoes",
            color_continuous_scale=["#EFE6DA", "#B54708", "#8B1E2D"],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            height=340, xaxis_title="Nº de reposições no dia", yaxis_title="",
            coloraxis_showscale=False, margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "A métrica que o cliente disse ser a mais valiosa: 'se o arroz foi reposto cinco "
            "vezes, já é um dado bastante relevante'. Custo de implementar: um botão."
        )
    else:
        st.info("Nenhuma reposição registrada.")

st.divider()

col_e, col_f = st.columns([1, 1])

with col_e:
    st.subheader("Alertas ativos")
    if not alertas:
        st.success("Nenhum alerta. Operação dentro das metas.")
    for alerta in alertas:
        st.markdown(
            f'<div class="alerta alerta-{alerta["severidade"]}">'
            f'<div class="alerta-titulo">{alerta["tipo"].replace("_", " ").title()} · '
            f'{alerta["severidade"].upper()}</div>'
            f'<div class="alerta-msg">{alerta["mensagem"]}</div></div>',
            unsafe_allow_html=True,
        )
    if st.button("Registrar alertas no histórico", use_container_width=True):
        with sessao() as s:
            novos = servico.registrar_alertas(s, alertas)
        st.success(f"{novos} alerta(s) registrado(s). Cooldown de 15 min por tipo.")

with col_f:
    st.subheader("Mesas aguardando higienização")
    if sujas:
        st.dataframe(
            pd.DataFrame(sujas).rename(
                columns={
                    "id": "mesa",
                    "nivel": "nível",
                    "lugares": "lugares",
                    "minutos_livre": "min livre",
                    "prioridade": "prioridade",
                }
            )[["mesa", "nível", "lugares", "min livre", "prioridade"]],
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            "Prioridade = tempo livre × (lugares/4) × peso do nível. "
            "Mesa grande no salão principal primeiro."
        )
    else:
        st.success("Nenhuma mesa pendente.")

st.divider()
st.subheader("Simulador de cenário")
st.caption(
    "Move o mix premium e mostra o efeito na margem. É a conversa que o dado permite ter "
    "com a cozinha: 'vale a pena manter esta carne no buffet?'"
)

with sessao() as s:
    casos = {c.categoria: c.custo_kg for c in s.scalars(select(CategoriaCusto))}
custo_premium = casos.get("carne_premium", 79.0)
custo_base = casos.get("acompanhamento", 12.0)

deslocamento = st.slider(
    "Deslocamento do mix: sai de acompanhamento, entra em carne premium (p.p.)",
    min_value=-10,
    max_value=10,
    value=0,
    step=1,
)
peso_medio_kg = (ind["peso_medio_g"] or 550) / 1000
delta_por_prato = (deslocamento / 100) * (custo_premium - custo_base) * peso_medio_kg
impacto_dia = -delta_por_prato * ind["comandas"]

c1, c2, c3 = st.columns(3)
c1.metric("Impacto por prato", brl(-delta_por_prato))
c2.metric("Impacto no dia", brl(impacto_dia), f"{ind['comandas']} comandas")
c3.metric("Projeção mensal (22 dias)", brl(impacto_dia * 22))
st.caption(
    f"Premissa: prato médio de {peso_medio_kg * 1000:.0f} g; diferença de custo de "
    f"{brl(custo_premium)} para {brl(custo_base)} por kg. Oportunidade estimada, não retorno garantido."
)

rodape_dados_sinteticos()
