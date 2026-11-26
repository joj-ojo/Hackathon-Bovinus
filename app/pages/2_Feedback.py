"""Totem/QR de feedback: 1-clique + Pergunta do Dia, vinculado à comanda."""

from __future__ import annotations

import pathlib
import sys

_RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _caminho in (_RAIZ, _RAIZ / "app"):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import streamlit as st  # noqa: E402

from ui import garantir_dados, pct, setup  # noqa: E402

setup("Feedback", layout="centered")

from core import servico  # noqa: E402
from core.db import sessao  # noqa: E402

garantir_dados()

st.markdown("<h1 style='text-align:center'>Como foi seu almoço?</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center;color:#6B6259'>Um toque. Dois segundos. Sem cadastro, sem login.</p>",
    unsafe_allow_html=True,
)

with sessao() as s:
    sugestao = servico.proximo_numero(s)
    pergunta = servico.pergunta_do_dia(s)

comanda = st.text_input(
    "Número da comanda (está impresso no cartão)", value=st.session_state.get("fb_comanda", sugestao)
)
st.session_state["fb_comanda"] = comanda
st.caption("No totem real este campo vem do código de barras. No QR, vem na URL.")

for chave in ("fb_nota", "fb_item_nota", "fb_resto"):
    st.session_state.setdefault(chave, None)
st.session_state.setdefault("fb_ok", None)

NOTAS = [
    (1, "😞", "Ruim"),
    (2, "🙁", "Fraco"),
    (3, "🙂", "Bom"),
    (4, "😄", "Ótimo"),
]

if st.session_state["fb_ok"]:
    st.success("Obrigado! Sua avaliação foi registrada na sua comanda.")
    st.balloons()
    with sessao() as s:
        resumo = servico.resumo_comanda(s, st.session_state["fb_ok"]["comanda"])
    if resumo and resumo["pratos"]:
        st.markdown("#### O que tinha no seu prato")
        itens = resumo["pratos"][0]["itens"]
        for item in itens:
            st.progress(
                min(1.0, item["percentual"]),
                text=f"{item['rotulo'] or item['categoria']} — {pct(item['percentual'] * 100, 0)}",
            )
        st.caption(
            "Esse retorno ajuda a cozinha a decidir o que continua no buffet. "
            "Nenhum dado pessoal é coletado."
        )
    if st.button("Avaliar outra comanda", use_container_width=True):
        st.session_state.update(
            {"fb_nota": None, "fb_item_nota": None, "fb_resto": None, "fb_ok": None}
        )
        st.rerun()
    st.stop()

if st.session_state["fb_nota"] is None:
    st.markdown("### 1. De 0 a 4, como foi?")
    colunas = st.columns(4)
    for col, (valor, emoji, rotulo) in zip(colunas, NOTAS, strict=False):
        with col:
            if st.button(
                f"{emoji}\n\n{rotulo}",
                key=f"nota_{valor}",
                use_container_width=True,
            ):
                st.session_state["fb_nota"] = valor
                st.rerun()
    st.stop()

escolhida = next(n for n in NOTAS if n[0] == st.session_state["fb_nota"])
st.markdown(f"### Sua nota: {escolhida[1]} {escolhida[2]}")
st.progress(st.session_state["fb_nota"] / 4)

if st.session_state["fb_item_nota"] is None:
    st.markdown(f"### 2. E o **{pergunta['item']}** de hoje?")
    st.caption(f"Pergunta do dia escolhida automaticamente: {pergunta['motivo']}.")
    colunas = st.columns(4)
    for col, (valor, emoji, rotulo) in zip(colunas, NOTAS, strict=False):
        with col:
            if st.button(emoji, key=f"item_{valor}", use_container_width=True):
                st.session_state["fb_item_nota"] = valor
                st.rerun()
    if st.button("Não comi esse item", use_container_width=True):
        st.session_state["fb_item_nota"] = 0
        st.rerun()
    st.stop()

if st.session_state["fb_resto"] is None:
    st.markdown("### 3. Sobrou comida no prato?")
    colunas = st.columns(3)
    opcoes = [("nada", "Nada"), ("pouco", "Um pouco"), ("muito", "Muito")]
    for col, (valor, rotulo) in zip(colunas, opcoes, strict=False):
        with col:
            if st.button(rotulo, key=f"resto_{valor}", use_container_width=True):
                st.session_state["fb_resto"] = valor
                st.rerun()
    st.stop()

comentario = st.text_area("Quer deixar um comentário? (opcional)", max_chars=280)

if st.button("Enviar avaliação", type="primary", use_container_width=True):
    nota_item = st.session_state["fb_item_nota"] or None
    with sessao() as s:
        servico.criar_comanda(s, numero=comanda)
        servico.registrar_feedback(
            s,
            comanda_numero=comanda,
            nota_geral=st.session_state["fb_nota"],
            item=pergunta["item"] if nota_item else None,
            nota_item=nota_item,
            resto=st.session_state["fb_resto"],
            comentario=comentario or None,
            canal="totem",
        )
    st.session_state["fb_ok"] = {"comanda": comanda}
    st.rerun()

st.divider()
with st.expander("O que acontece com esse dado"):
    st.markdown(
        """
- A nota entra no **ranking de itens** do painel gerencial.
- A pergunta do dia é escolhida sozinha: o item com **menor nota** dos últimos 3 dias.
- O "sobrou?" alimenta a estimativa de **resto ingesto** — que hoje é zero.
- O número da comanda liga o feedback ao **mix do prato** e ao **CMV**. É esse cruzamento
  que responde "esta lasanha vale a pena?".
        """
    )
