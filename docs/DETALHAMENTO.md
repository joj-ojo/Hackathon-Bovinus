# Detalhamento técnico

> Complemento do [README](../README.md): como a solução foi pensada e construída.
> Para decisões, riscos e plano de 48 h, veja o [Plano técnico](PLANO-TECNICO.md); para os fatos
> ditos pelo cliente, os [Achados da palestra](ACHADOS-DA-PALESTRA.md).

---

## As telas

| Página | Para quem | O que faz |
|---|---|---|
| **Balança** | operador | foto do prato → composição → CMV → salva na comanda, com correção em 2 segundos |
| **Feedback** | cliente | 4 carinhas + Pergunta do Dia + "sobrou?" — mobile-first, QR ou totem |
| **Painel** | gerente | CMV por hora, mix × satisfação, fila, cubas, alertas, simulador de cenário |
| **Mesas** | garçom/metre | mapa do salão, cronômetro, prioridade de higienização, +1 reposição de cuba |
| **Comandas** | demonstração | do número da comanda ao prato, à margem e à avaliação |

Roteiro do vídeo de 2 minutos: [`ROTEIRO-VIDEO.md`](ROTEIRO-VIDEO.md).

---

## Como o CMV é calculado

A foto dá **área**; a balança dá **peso total**. Área não é peso — 100 cm² de salada pesam
muito menos que 100 cm² de picanha. A conversão normaliza por densidade superficial:

```
peso_i = peso_total × (a_i · d_i) / Σ(a_j · d_j)
```

```
custo_prato    = Σ (peso_i × custo_kg_i)
receita_prato  = peso_total × R$ 119,00
cmv_pct        = custo_prato / receita_prato
margem_comanda = receita_prato + bebidas − custo_prato − 0,30 × bebidas
```

Exemplo real do sistema: 550 g, mix 25% premium / 10% média / 20% ave / 25% acompanhamento /
15% salada / 5% sobremesa → **custo R$ 35,45/kg → CMV 29,8%**, margem R$ 45,95 no prato.

> A tabela de custo por kg é **premissa explícita** (estimativas de atacado/CEASA), porque o
> restaurante não usa ficha técnica no dia a dia. O CMV é uma estimativa de gestão, não
> contabilidade.

### Categorias

`carne_premium` · `carne_media` · `ave_suino` · `acompanhamento` · `massa_risoto` ·
`fritura_empanado` · `salada_legume` · `sobremesa` · `outros`

---

## Arquitetura

```
balança/câmera ──► percepção (foto + peso + comanda) ──► motor (CMV, filas, mesas, alertas)
câmeras Intelbras ─┘                                              │
                                                                  ▼
                                        SQLite (demo) / Supabase (produção)
                                                                  │
                    ┌──────────────┬──────────────┬───────────────┴──────┐
                 Totem/QR       Painel         Mesas                API FastAPI
                (Streamlit)   (Streamlit)    (Streamlit)        /pratos /feedback /webhooks
```

Decisões que sustentam a demo:

- **VLM como primário, OpenCV como rede de segurança**: o demo funciona sem internet.
- **YOLO11n pré-treinado só para pessoas** (filas e mesas) — zero treinamento necessário.
- **SQLite no demo, Postgres/Supabase em produção**, via `DATABASE_URL` (SQLAlchemy).
- **Streamlit para tudo** e FastAPI fino reaproveitando o mesmo `core/`.

### Integração com o JS Softcom (não invasiva)

| Caminho | Como | Dependência |
|---|---|---|
| **A · Conector de borda** ✅ implementado | captura `(comanda, peso, foto)` na balança | nenhuma |
| **B · Espelho/importação** | leitura somente-leitura do banco local ou CSV | baixa |
| **C · API/Webhook** | `POST /webhooks/comanda` com `aberta` / `item.lancado` / `fechada` | do fornecedor |

O endpoint do caminho C já existe em `api/main.py` e é funcional como simulador. A recepção
humanizada e o caixa continuam exatamente como estão.

---

## Números que sustentam o pitch

| Alavanca | Conta | Ordem de grandeza |
|---|---|---|
| 1 p.p. de mix premium | R$ 61/kg de diferença × 0,55 kg × 600 pratos | **~R$ 205/dia** |
| Fila na escada | 3% de 420 clientes do pico × ticket R$ 80 | **~R$ 1,0 mil/dia** |
| 2 min a menos de mesa suja | 100 mesas × 5 lugares × 2 min ÷ 37 min de permanência | **~27 clientes/dia** |
| Hardware | 3 câmeras USB + suportes + iluminação | **R$ 1.320 – 2.820** |

Tudo é **oportunidade estimada**, com premissas explícitas — não retorno garantido. O próprio
cliente disse em palestra que não há promessa de ROI.

Lei de Little, que transforma fila em tempo: `W = L / λ`. Com 8,6 chegadas/min e meta de
2,5 min, a fila não pode passar de **21 pessoas**; a fila de 4 min medida equivale a ~34.

---

## Estrutura

```
app/                  # Streamlit (5 páginas) + ui.py
core/                 # domínio, sem dependência de UI
  cmv.py              # motor de custo e margem
  vision/             # VLM (gemini/openai) + heurística OpenCV + pipeline
  fluxo.py            # Lei de Little, prioridade de mesa
  alertas.py          # regras puras de alerta
  servico.py          # consultas e regras de negócio
  seed.py             # 3 dias de operação sintética
  demo.py             # pratos sintéticos + CMV esperado
api/main.py           # FastAPI
scripts/              # verificar, gerar pratos, avaliar modelo, processar vídeo
tests/                # CMV e fluxo
docs/                 # plano técnico, achados, roteiro do vídeo
data/                 # banco local, fotos, ROIs de exemplo
```

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | status |
| GET | `/api/v1/indicadores?dia=` | KPIs do dia |
| POST | `/api/v1/pratos/analisar` | foto + peso → composição e CMV (`persistir=true` grava) |
| POST | `/api/v1/feedback` | feedback vinculado à comanda |
| POST | `/api/v1/comandas` | abre comanda |
| GET | `/api/v1/comandas/{numero}` | comanda completa |
| GET | `/api/v1/alertas` | alertas ativos |
| GET | `/api/v1/fila` | fila atual por zona |
| POST | `/webhooks/comanda` | contrato de integração com o SaaS |

Contrato do prato:

```json
{
  "comanda": "0421",
  "peso_total_g": 612,
  "confianca_global": 0.78,
  "modelo": "vlm:gemini-2.5-flash",
  "status": "ok",
  "itens": [
    {"categoria": "carne_premium", "rotulo": "picanha", "percentual_area": 0.18,
     "peso_estimado_g": 128, "custo_kg": 79.0, "custo": 10.11}
  ],
  "cmv": {"custo_total": 16.42, "receita": 72.83, "cmv_pct": 22.5, "margem_bruta": 56.41},
  "mix_premium_pct": 0.18
}
```

---

## Dados e premissas

- Todos os dados do demo são **sintéticos**, calibrados com os números da operação
  (600 clientes/dia útil, pico 12h10–13h20, 90 mesas, R$ 119/kg, fila de 4 min medida,
  meta de 2,5 min). Nenhum dado pessoal de cliente é usado.
- Os custos por kg são estimativas de atacado e estão visíveis na interface.
- O pipeline de visão devolve `status: revisar` abaixo de 0,55 de confiança e permite
  correção humana — o dado nunca entra "cego".

### LGPD

- Câmera da balança é **top-down no prato**, sem captura de rosto.
- Câmeras de salão são usadas apenas para **contagem agregada de pessoas**, sem
  reconhecimento facial e sem identificação individual.
- Fotos de prato: retenção curta (7 dias no modo produção) e armazenamento em 640 px WebP.
- Feedback é anônimo, vinculado apenas ao número da comanda.

---

## Limitações conhecidas

1. A precisão do mix depende da qualidade da foto e da calibração; o número de MAPE deve ser
   medido com o protocolo de 20 pratos (`scripts/avaliar_modelo.py`).
2. A integração real com o JS Softcom não foi implementada — só o conector de borda e o
   contrato do webhook.
3. O seed tem 180 comandas/dia (não 600) para manter a demo leve.
4. As ROIs de câmera usam um frame de referência; precisam ser desenhadas na planta real.
5. Não há autenticação: é um protótipo de hackathon.

## Roadmap

- Treinar segmentação própria (YOLO11-seg) com o vídeo de 1h30 da casa + frames anotados.
- Estimar resto por área no prato na saída (segunda foto ou QR).
- Conector real com o SaaS e conciliação automática de bebidas.
- Mapa de calor do salão e previsão de demanda por dia da semana.
- Alerta de fila acionando ação operacional (reforço de churrasqueira / desconto de horário).
