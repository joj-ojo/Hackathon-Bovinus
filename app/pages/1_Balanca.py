"""Página da balança: foto → composição → CMV."""

from __future__ import annotations

import base64
import pathlib
import sys

_RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _caminho in (_RAIZ, _RAIZ / "app"):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from ui import brl, garantir_dados, grade_kpis, link_pagina, pct, setup  # noqa: E402

setup("Balança")

from core import servico  # noqa: E402
from core.custos import CATEGORIAS_PADRAO, LISTA_CATEGORIAS  # noqa: E402
from core.db import sessao  # noqa: E402
from core.demo import gerar_todas  # noqa: E402
from core.vision import (  # noqa: E402
    analisar_bytes,
    analisar_manual,
    persistir_pesagem,
    salvar_foto,
)

garantir_dados()

st.title("Balança · o que o cliente colocou no prato")
st.caption(
    "A balança só sabe o peso. A câmera no prato diz a composição. Juntos, viram CMV em reais."
)

with sessao() as s:
    sugestao = servico.proximo_numero(s)

st.session_state.setdefault("b_analise", None)

col_esq, col_dir = st.columns([1, 1.15])

with col_esq:
    comanda = st.text_input("Número da comanda", value=st.session_state.get("b_comanda", sugestao))
    peso_g = st.number_input(
        "Peso na balança (g)", min_value=50, max_value=2500, value=560, step=10
    )
    balanca = st.selectbox("Balança", ["B1", "B2", "B3"])

    origem = st.radio(
        "Origem da foto", ["Enviar arquivo", "Câmera", "Prato de demonstração"],
        horizontal=True,
    )

    foto_bytes: bytes | None = None
    if origem == "Enviar arquivo":
        arquivo = st.file_uploader("Foto do prato (vista de cima)", type=["jpg", "jpeg", "png", "webp"])
        if arquivo:
            foto_bytes = arquivo.getvalue()
    elif origem == "Câmera":
        captura = st.camera_input("Posicione o prato sob a câmera")
        if captura:
            foto_bytes = captura.getvalue()
    else:
        pratos = gerar_todas()
        escolhido = st.selectbox("Prato", pratos, format_func=lambda p: p["titulo"])
        foto_bytes = pathlib.Path(escolhido["caminho"]).read_bytes()

    if foto_bytes:
        st.image(foto_bytes, caption="Foto que será analisada", use_container_width=True)

    analisar = st.button("Analisar prato", type="primary", use_container_width=True)

if analisar:
    if not foto_bytes:
        st.warning("Selecione ou capture uma foto do prato.")
    else:
        with st.spinner("Analisando composição do prato…"):
            st.session_state["b_analise"] = analisar_bytes(foto_bytes, float(peso_g))
            st.session_state["b_foto"] = foto_bytes
            st.session_state["b_peso"] = float(peso_g)
            st.session_state["b_comanda"] = comanda

res = st.session_state["b_analise"]

with col_dir:
    if not res:
        st.info(
            "Envie a foto do prato para ver a composição estimada, o custo e a margem. "
            "Sem chave de API o sistema usa o modo heurístico — de propósito, para a demo "
            "nunca depender de internet."
        )
    else:
        st.markdown("#### Resultado da análise")
        c1, c2 = st.columns(2)
        with c1:
            st.image(st.session_state["b_foto"], caption="Original", use_container_width=True)
        with c2:
            overlay = res.get("overlay_png_b64")
            if overlay:
                st.image(
                    base64.b64decode(overlay),
                    caption="Segmentação (heurística offline)",
                    use_container_width=True,
                )
            else:
                st.caption("Segmentação visual disponível no modo heurístico.")

        status = {"ok": "✅ ok", "revisar": "⚠️ revisar", "manual": "✍️ manual"}[res["status"]]
        st.caption(
            f"Modelo: `{res['modelo']}` · confiança {res['confianca_global']:.2f} · "
            f"{res['latencia_ms']} ms · status {status}"
        )

        grade_kpis(
            [
                (pct(res["cmv"]["cmv_pct"], 1), "CMV do prato", "custo / receita"),
                (brl(res["cmv"]["custo_total"]), "Custo estimado", "tabela de custo/kg"),
                (brl(res["cmv"]["receita"]), "Receita", f"{res['peso_total_g']} g × R$ 119/kg"),
                (brl(res["cmv"]["margem_bruta"]), "Margem bruta", "antes de bebida"),
            ],
            colunas=4,
        )

if res:
    st.divider()
    st.subheader("Composição — ajuste se precisar")
    st.caption(
        "O operador de balança pode corrigir em 2 segundos. O modelo aprende com a correção "
        "e o CMV continua confiável."
    )

    df = pd.DataFrame(
        [
            {
                "categoria": i["categoria"],
                "rotulo": i.get("rotulo", ""),
                "percentual_area": round(i["percentual_area"], 3),
            }
            for i in res["itens"]
        ]
    )
    if df.empty:
        df = pd.DataFrame([{"categoria": "carne_premium", "rotulo": "", "percentual_area": 0.3}])

    editado = st.data_editor(
        df,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        key=f"editor_{res['prato_id']}",
        column_config={
            "categoria": st.column_config.SelectboxColumn(
                "Categoria", options=list(CATEGORIAS_PADRAO), required=True
            ),
            "rotulo": st.column_config.TextColumn("Rótulo", width="medium"),
            "percentual_area": st.column_config.NumberColumn(
                "Área (%)", min_value=0.0, max_value=1.0, step=0.01, format="%.3f"
            ),
        },
    )

    composicao: dict[str, float] = {}
    for _, linha in editado.iterrows():
        if linha["percentual_area"] and linha["percentual_area"] > 0:
            composicao[linha["categoria"]] = (
                composicao.get(linha["categoria"], 0.0) + float(linha["percentual_area"])
            )

    ajustado = analisar_manual(composicao, float(st.session_state["b_peso"]))
    total_area = sum(composicao.values())

    c1, c2, c3 = st.columns([1, 1, 1.2])
    c1.metric("CMV ajustado", pct(ajustado["cmv"]["cmv_pct"], 1))
    c2.metric("Custo ajustado", brl(ajustado["cmv"]["custo_total"]))
    c3.metric("Margem ajustada", brl(ajustado["cmv"]["margem_bruta"]))

    if abs(total_area - 1.0) > 0.02:
        st.warning(f"A área soma {total_area:.2f} — o motor normaliza para 100% automaticamente.")
    if ajustado["mix_premium_pct"] > 0.25:
        st.error(
            f"Mix premium em {ajustado['mix_premium_pct'] * 100:.0f}% do prato. "
            "Cada ponto percentual aqui custa cerca de R$ 0,34 de margem."
        )

    if st.button("Salvar pesagem na comanda", type="primary"):
        with sessao() as s:
            numero = st.session_state["b_comanda"]
            servico.criar_comanda(s, numero=numero)
            caminho = salvar_foto(st.session_state["b_foto"])
            persistir_pesagem(
                s, numero, ajustado, foto_path=caminho, balanca_id=balanca
            )
        st.success(f"Pesagem gravada na comanda {numero}.")
        link_pagina("pages/5_Comandas.py", label="Ver a comanda ponta a ponta →")

st.divider()
st.subheader("Mesmo peso, margens diferentes")
st.caption(
    "Três pratos de demonstração analisados pelo pipeline real (modo offline). "
    "É esse número que o restaurante nunca teve."
)

pratos = gerar_todas()
colunas = st.columns(3)
for col, prato in zip(colunas, pratos, strict=False):
    with col:
        st.image(str(prato["caminho"]), use_container_width=True)
        st.markdown(f"**{prato['titulo']}** · {prato['peso_g']} g")
        st.caption(prato["descricao"])
        st.metric("CMV esperado", pct(prato["cmv"]["cmv_pct"], 1))
        if st.button("Analisar com IA", key=f"demo_{prato['nome']}", use_container_width=True):
            resultado = analisar_bytes(prato["caminho"].read_bytes(), prato["peso_g"], provider="heuristica")
            st.metric("CMV detectado", pct(resultado["cmv"]["cmv_pct"], 1))

with st.expander("Fallback manual (se a foto falhar)"):
    st.caption("Três chips e o CMV aproximado. A operação nunca fica sem resposta.")
    proteina = st.slider("Proteína (% do prato)", 0, 100, 30, key="m_prot")
    carbo = st.slider("Carboidrato/acompanhamento (%)", 0, 100, 45, key="m_carbo")
    salada = 100 - proteina - carbo
    st.write(f"Salada e outros: **{max(0, salada)}%**")
    manual = analisar_manual(
        {
            "carne_premium": max(0, proteina) / 100,
            "acompanhamento": max(0, carbo) / 100,
            "salada_legume": max(0, salada) / 100,
        },
        float(peso_g),
    )
    st.metric("CMV aproximado", pct(manual["cmv"]["cmv_pct"], 1))

with st.expander("Categorias e custo por kg (editável no código, premissa do projeto)"):
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "categoria": c,
                    "rótulo": d["rotulo"],
                    "custo_kg": d["custo_kg"],
                    "densidade_g_cm2": d["densidade"],
                }
                for c, d in CATEGORIAS_PADRAO.items()
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "O restaurante não usa ficha técnica no dia a dia; estes valores são estimativas de "
        "atacado e ficam explícitos no pitch. O CMV é uma estimativa, não uma contabilidade."
    )
