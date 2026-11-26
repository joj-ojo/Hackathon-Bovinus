# Plano Técnico — Sistema de Inteligência Operacional Bovinu's Grill & Beer

> Hackathon FMU 2026 · Unidade Augusta · Entrega **quinta 26/11 às 12h00**
> Documento irmão: [`ACHADOS-DA-PALESTRA.md`](./ACHADOS-DA-PALESTRA.md) (fatos e números ditos pelo cliente)

---

## 0. A tese em uma frase

Não integramos com o sistema de comandas do restaurante: **anexamos uma camada de percepção ao ponto onde o dado nasce** — a balança — e devolvemos decisão em três telas (operador, cliente, gestor), usando o **número da comanda como chave única** e **zero alteração no caixa, na recepção ou no SaaS**.

Todo o resto (visão computacional, CMV, filas, mesas, feedback) é consequência dessa escolha. Ela é o que torna o projeto viável em 48h *e* vendável depois.

### Por que não depender do JS Softcom

O cliente não sabe se o sistema tem API; o servidor é local; não há documentação pública. Apostar a entrega nisso é risco desnecessário. Nossa arquitetura tem **três caminhos de integração, do mais barato ao mais completo**:

| Caminho | Como funciona | Dependência | Quando usar |
|---|---|---|---|
| **A. Conector de borda (MVP)** ✅ | Um agente na balança captura `(nº comanda, peso, foto)` no ato da pesagem. Não conversa com o SaaS. | Nenhuma | MVP e produção inicial |
| **B. Importação/espelho (fase 2)** | Leitura somente-leitura do banco local ou export CSV/planilha do JS Softcom. | Baixa | Enriquecer com bebidas e fechamento |
| **C. API/Webhook (ideal)** | `POST /webhooks/comanda` com eventos `aberta` / `item.lancado` / `fechada`. | Alta (depende do fornecedor) | Quando o fornecedor abrir |

O MVP entrega **A** funcionando + **C** especificado e simulado. Isso protege a demo e mostra maturidade de arquitetura.

---

## 1. Arquitetura

```
                 ┌──────────────────────────────────────────────────────┐
   BALANÇA       │  CAMADA DE PERCEPÇÃO (edge, no servidor local)       │
   ┌────────┐    │  • trigger da pesagem (barcode/peso estabilizado)    │
   │ comanda│───▶│  • captura da foto (top-down, sem rosto)             │
   │ peso   │    │  • inferência: VLM → JSON de composição              │
   └────────┘    │  • fallback local OpenCV (HSV/área) se offline       │
                 └──────────────────────┬───────────────────────────────┘
                                        │ (comanda, peso, itens, confiança)
   CÂMERAS       ┌──────────────────────▼───────────────────────────────┐
   Intelbras ───▶│  MOTOR DE INTELIGÊNCIA (Python)                      │
   (RTSP/ROI)    │  • CMV/margem por prato e por comanda                │
                 │  • filas (ROI + Little's Law)                        │
                 │  • mesas (ocupação + latência de higienização)       │
                 │  • regras de alerta com cooldown                     │
                 └──────┬───────────────────────────┬───────────────────┘
                        │                           │
              ┌─────────▼─────────┐       ┌─────────▼──────────┐
              │  Postgres         │       │  API (FastAPI)     │
              │  Supabase (prod)  │       │  /pratos /feedback │
              │  SQLite (demo)    │       │  /alertas /webhooks│
              └─────────┬─────────┘       └─────────┬──────────┘
                        │                           │
        ┌───────────────┴───────────────┬───────────┴────────────┐
        │                               │                        │
 ┌──────▼──────┐                 ┌──────▼──────┐          ┌──────▼──────┐
 │ TOTEM / QR  │                 │  PAINEL     │          │  MESAS      │
 │ cliente     │                 │  GERENCIAL  │          │  (garçom)   │
 │ (Streamlit) │                 │ (Streamlit) │          │ (Streamlit) │
 └─────────────┘                 └─────────────┘          └─────────────┘
```

**Decisão de stack (alinhada ao escopo, com foco em demo que não cai):**

| Camada | Escolha | Por quê |
|---|---|---|
| UI + painel | **Streamlit** multipage + Plotly | Escopo pede; entrega 4 telas em horas |
| API | **FastAPI** fino, reaproveitando o mesmo `core/` | Demonstra integração sem duplicar lógica |
| Banco | **SQLAlchemy** com `DATABASE_URL`; **SQLite no demo**, **Supabase (Postgres) em prod** | Se a internet cair na apresentação, nada quebra |
| Visão | **VLM (Gemini 2.5 Flash / GPT-4o-mini)** como primário + **OpenCV** como fallback + **YOLO11n pré-treinado** (pessoas) para filas/mesas | Sem dataset rotulado em 48h, treinar segmentação de comida é aposta. YOLO pré-treinado resolve fila/mesa com zero treino |
| Deploy | Render (API) + Streamlit Cloud/local | Escopo pede Render |
| Fotos | disco local no demo / Supabase Storage em prod, 640px WebP | 600 fotos/dia × 40KB ≈ 24MB/dia → retenção de 7 dias |

### Por que VLM e não YOLO custom no prato

- Não temos dataset rotulado. O vídeo de 1h30 está prometido, não entregue.
- O VLM devolve **JSON estruturado já no vocabulário de negócio** ("picanha", "arroz", "salada") — exatamente o entregável pedido no escopo.
- Custo: ~600 pratos/dia. Com imagem de ~250–400 tokens, fica na casa de **centavos por dia** (≪ R$0,01/prato). Irrelevante frente a R$119/kg.
- YOLO custom (8 classes, segmentação) entra no roadmap com o vídeo + frames anotados. **Documentar, não construir agora.**

---

## 2. Do pixel ao CMV (o núcleo do projeto)

### 2.1 O problema físico

A balança dá **um número**: peso total. A foto dá **proporção de área**. Densidades diferentes fazem área ≠ peso. A conversão correta é uma normalização por densidade superficial:

```
peso_i = peso_total × (a_i · d_i) / Σ(a_j · d_j)
```

- `a_i` = fração de área ocupada pela categoria i (segmentação)
- `d_i` = gramas por cm² de superfície empilhada (tabela calibrada por categoria: salada ~0,5 · massa ~1,0 · arroz ~1,1 · feijão ~1,2 · carne ~1,5)

Isso é fisicamente defensável e **explicável para a banca** — muito melhor que "o modelo acha que é 30% de picanha".

Calibração de área: prato de diâmetro fixo + câmera em altura fixa ⇒ máscara circular do prato dá a escala px→cm². A 0,6 m de altura, uma câmera Full HD entrega ~2 px/mm (prato de 26 cm ≈ 500 px de diâmetro) — folgado para segmentação.

### 2.2 Motor de CMV

```
custo_prato   = Σ (peso_i × custo_kg_i)
receita_prato = peso_total × R$ 119,00
cmv_pct       = custo_prato / receita_prato
margem_prato  = receita_prato − custo_prato
margem_comanda= receita_prato + receita_bebidas − custo_prato − custo_bebidas
```

Tabela `categorias_custo` **editável na própria interface** (eles não usam ficha técnica — vamos assumir preços de atacado/CEASA e dizer isso na tela). Valores iniciais plausíveis (R$/kg de prato pronto):

| Categoria | Custo/kg | Exemplos |
|---|---|---|
| `carne_premium` | 79,00 | picanha, filé, maminha |
| `carne_media` | 45,00 | costela, cupim, alcatra |
| `ave_suino` | 22,00 | frango, linguiça, lombo |
| `acompanhamento` | 12,00 | arroz, feijão, farofa, purê |
| `salada_legume` | 16,00 | folhas, legumes, saladas frias |
| `massa_risoto` | 18,00 | massas, risotos |
| `fritura_empanado` | 25,00 | à milanesa, bolinho, batata |
| `sobremesa` | 28,00 | doces, frutas |

Sanidade: prato de 550 g com mix 25% premium / 10% média / 20% ave / 25% acompanhamento / 15% salada / 5% sobremesa → **R$ 35,45/kg de custo** → CMV **29,8%**, margem **R$ 45,95** no prato. Números coerentes com food cost de self-service (28–35%).

### 2.3 Contrato do JSON (entregável explícito do escopo)

`POST /api/v1/pratos/analisar` (multipart: `foto`, `comanda`, `peso_g`)

```json
{
  "prato_id": "0f0c...",
  "comanda": "0421",
  "peso_total_g": 612,
  "confianca_global": 0.78,
  "modelo": "gemini-2.5-flash",
  "latencia_ms": 1180,
  "itens": [
    { "categoria": "carne_premium", "rotulo": "picanha", "percentual_area": 0.18,
      "peso_estimado_g": 128, "custo_kg": 79.0, "custo": 10.11, "confianca": 0.82 },
    { "categoria": "acompanhamento", "rotulo": "arroz branco", "percentual_area": 0.34,
      "peso_estimado_g": 240, "custo_kg": 12.0, "custo": 2.88, "confianca": 0.91 }
  ],
  "cmv": { "custo_total": 16.42, "receita": 72.83, "cmv_pct": 22.5, "margem_bruta": 56.41 },
  "alertas": ["mix_premium_alto"]
}
```

Regras de robustez embutidas:
- `confianca_global < 0.55` ⇒ `status: "revisar"` e a tela do operador abre os chips de correção.
- Timeout do VLM (>4 s) ou sem rede ⇒ **fallback OpenCV** (máscaras HSV por família de cor + área) e marca `modelo: "heuristico"`.
- Foto falha/escura ⇒ **fallback humano**: 3 chips (proteína / acompanhamento / salada) + peso ⇒ CMV aproximado. **A demo nunca fica sem resposta.**

---

## 3. As 4 dores → 4 módulos

### DOR 1 — Mix do prato e CMV (crítica)

| | |
|---|---|
| **Telas** | `Balança` (operador) e drill-down no `Painel` |
| **Entrada** | foto + peso + comanda (câmera USB ou upload; webcam do notebook no demo) |
| **Saída** | composição %, CMV, margem, alerta de mix |
| **Valor para o pitch** | 1 p.p. de mix premium ≈ **R$ 0,34/prato** ≈ **R$ 205/dia** (600 pratos) ≈ **R$ 4,5 mil/mês** (22 dias). 5 p.p. ≈ R$ 1 mil/dia |
| **Prova** | protocolo de validação: compor 20 pratos com componentes **pesados separadamente** na balança, fotografar, comparar. Reportar MAPE do CMV |

### DOR 2 — Filas e tempo do cliente executivo

| | |
|---|---|
| **Telas** | `Painel` (timeline de fila + alertas) |
| **Entrada** | vídeo/câmeras Intelbras existentes + ROIs desenhados uma vez |
| **Método** | YOLO11n (pessoas, COCO, sem treino) → contagem por ROI a cada 2 s → `λ` (chegadas/min) → **Lei de Little**: `W = L/λ` |
| **Alertas** | `FILA_ESCADA` (lotação na ROI de entrada > limiar por 60 s = risco de desistência), `FILA_CHURRASQUEIRA` (W > 3 min) |
| **Sanidade numérica** | 600 clientes em 70 min ⇒ λ ≈ 8,6/min. Meta de 2,5 min ⇒ fila máxima ≈ **21 pessoas** (L = λ·W). A fila de 4 min medida corresponde a ~34 pessoas. Isso transforma "sensação" em **capacidade necessária** — ótimo slide |
| **Extra** | cruzar fila com o desconto de 10% das 11h30–12h para medir se a alavanca funciona |

### DOR 3 — Limpeza de mesas / giro do salão

| | |
|---|---|
| **Telas** | `Mesas` (garçom/gerente) e card no `Painel` |
| **Entrada** | ROI por mesa (subconjunto visível do salão) + botão "higienizada" no celular |
| **Estado** | `ocupada` → (sem pessoa por 30 s) → `livre` → (toque do garçom) → `limpa`; mede-se `livre → limpa` |
| **Alerta** | `MESA_SUJA` após 3 min, ranqueado por (tempo, nº de lugares, nível) — prioriza mesa grande no salão principal |
| **Valor** | 100 mesas no pico × 5 lugares × 2 min economizados ≈ 1.000 lugares-minuto ≈ **~27 clientes** adicionais no pico ≈ **R$ 1,7 mil/dia** (premissas explícitas) |

> Como o restaurante tem 4 metros e 7–8 garçons experientes, o ganho não vem de "cobrar mais rápido", e sim de **priorizar a mesa certa** e **provar o gargalo com número**.

### DOR 4 — Qualidade, desperdício e giro de cubas

| | |
|---|---|
| **Telas** | `Feedback` (totem/QR) + `Painel` (ranking de itens) + `Cubas` (1 toque) |
| **Fluxo cliente** | QR no verso da comanda / totem de saída → **4 carinhas** (1 toque) → **Pergunta do Dia** sobre 1 item estratégico (1 toque) → opcional "sobrou muito / pouco / nada" |
| **Fluxo cozinha** | botão **"+1 reposição"** por cuba (1 toque no celular) — é a métrica que eles disseram ser a mais valiosa |
| **Cruzamento** | `vw_mix_satisfacao`: nota média por item × mix servido × reposições × CMV ⇒ "esta lasanha tem nota 2,1 e CMV 12%: ou conserta ou sai do buffet" |
| **Bônus** | o feedback volta como recompensa ao cliente ("seu prato estava 72% equilibrado"), o que aumenta a taxa de resposta |

**Pergunta do Dia** deve ser configurável no painel (item + dia), com default automático: o item de **menor nota** ou **menor giro** da semana anterior.

---

## 4. Modelo de dados

```sql
-- Chave única de tudo
create table comandas (
  numero        text primary key,          -- '0421' (4 dígitos)
  codigo_barras text,
  origem        text not null,             -- 'jssoftcom' | 'simulado'
  aberta_em     timestamptz not null,
  fechada_em    timestamptz,
  valor_pago    numeric(10,2)
);

create table pesagens (
  id             uuid primary key,
  comanda_numero text references comandas(numero),
  balanca_id     text,
  peso_g         int not null,
  preco_kg       numeric(10,2) not null default 119.00,
  foto_path      text,
  modelo         text,                     -- 'gemini-2.5-flash' | 'heuristico' | 'manual'
  confianca      numeric(4,3),
  custo_estimado numeric(10,2),
  receita_prato  numeric(10,2),
  cmv_pct        numeric(5,2),
  criado_em      timestamptz default now()
);

create table pesagem_itens (
  id              bigserial primary key,
  pesagem_id      uuid references pesagens(id) on delete cascade,
  categoria       text not null,
  rotulo          text,
  percentual_area numeric(5,4),
  peso_estimado_g int,
  custo_kg        numeric(10,2),
  custo           numeric(10,2),
  confianca       numeric(4,3)
);

create table categorias_custo (
  categoria  text primary key,
  custo_kg   numeric(10,2) not null,
  densidade  numeric(5,3) not null,        -- g/cm² de superfície
  atualizado_em timestamptz default now()
);

create table feedback (
  id             bigserial primary key,
  comanda_numero text references comandas(numero),
  nota_geral     smallint check (nota_geral between 1 and 4),
  item_perguntado text,
  nota_item      smallint check (nota_item between 1 and 4),
  resto          text,                     -- 'muito' | 'pouco' | 'nada'
  comentario     text,
  canal          text,                     -- 'totem' | 'qr'
  criado_em      timestamptz default now()
);

create table mesas (
  id serial primary key, nivel smallint, lugares smallint,
  poligono jsonb,                          -- ROI no frame de referência
  status text default 'livre',             -- livre | ocupada | suja | limpa
  ocupada_desde timestamptz, livre_desde timestamptz, higienizada_em timestamptz
);

create table eventos_fila (
  id bigserial primary key, zona text, pessoas int, chegadas_por_min numeric(6,2),
  espera_estimada_min numeric(5,2), criado_em timestamptz default now()
);

create table reposicoes_cuba (
  id bigserial primary key, item text, capacidade_kg numeric(6,2),
  comanda_operador text, criado_em timestamptz default now()
);

create table alertas (
  id bigserial primary key, tipo text, severidade text, entidade text,
  mensagem text, criado_em timestamptz default now(), resolvido_em timestamptz
);
```

Views analíticas: `vw_cmv_dia`, `vw_mix_satisfacao`, `vw_latencia_limpeza`, `vw_fila_hora`.

Seed: `data/comandas_demo.csv` com 3 dias × ~180 comandas (pico realista 12h10–13h20), 8 itens de cardápio, ~30 feedbacks, ~40 mesas. **Tudo marcado como sintético** no rodapé do painel.

---

## 5. Telas (5 páginas Streamlit)

| Página | Usuário | Conteúdo |
|---|---|---|
| **1 · Balança** | operador de balança | webcam/upload + nº comanda + peso → preview segmentado + JSON + chips de correção + "Confirmar". 3 pratos de demo pré-carregados (premium / equilibrado / carboidrato) |
| **2 · Feedback** | cliente | 4 carinhas gigantes → Pergunta do Dia → "sobrou?" → agradecimento com % de equilíbrio do prato. Mobile-first (QR) |
| **3 · Painel** | gerente | KPIs (CMV médio, margem/comanda, ticket, CSAT, espera p95, mesas sujas) + mix×satisfação + CMV por hora + ranking de itens + alertas ao vivo + timeline de fila |
| **4 · Mesas** | garçom/metre | planta simplificada 2 níveis, cores por status, cronômetro, ranking de prioridade, botão "higienizada" |
| **5 · Comandas** | demo/gestor | lista + drill-down: foto do prato, itens, CMV, bebidas, feedback — a "ponta a ponta" |

Detalhe de demo que vende: no drill-down da comanda, a foto original ao lado do overlay de segmentação e da margem. Em 5 segundos a banca entende o projeto.

---

## 6. Plano de execução (hoje é terça 24/11, 22h)

### Ter 24/11 — noite (2–3h) · Fundação
- [ ] Criar repo público + estrutura de pastas + `requirements.txt` + `.env.example`
- [ ] `core/db` (modelos + seed de comandas/cardápio/custos) e `core/cmv/engine.py` com teste unitário
- [ ] Testar captura de foto + prompt do VLM em 5 pratos reais → ajustar vocabulário de categorias
- [ ] Mover o tooling de transcrição para `tools/transcricao/` e escrever o README do projeto (hoje o README raiz é do transcritor)

### Qua 25/11 — manhã · O núcleo (DOR 1)
- [ ] Pipeline foto → JSON → CMV com fallback heurístico e fallback manual
- [ ] Página `Balança` completa + tabela de custos editável
- [ ] Protocolo de avaliação: 20 pratos, MAPE do mix e do CMV
- [ ] Contrato `/pratos/analisar` no FastAPI

### Qua 25/11 — tarde · Experiência e gestão (DOR 3 e 4)
- [ ] Página `Feedback` (totem + QR) e gravação por comanda
- [ ] `Mesas` com estados, cronômetro, priorização e alerta
- [ ] `Painel` v1: KPIs, mix×satisfação, ranking de itens, cubas
- [ ] Regras de alerta com cooldown (evitar fadiga de alerta)

### Qua 25/11 — noite · Fluxo e integração (DOR 2 + docs)
- [ ] `scripts/processar_video.py`: YOLO11n + ROIs no vídeo fornecido (ou num trecho de teste) → `eventos_fila` + vídeo anotado
- [ ] Timeline de fila + alerta de escada no painel
- [ ] `docs/ARQUITETURA.md`, `docs/CAMERAS.md` (planta + BOM), `docs/INTEGRACAO.md` (A/B/C + webhook), `docs/LGPD.md`
- [ ] Seed final de demonstração coerente (histórias que contam: "terça do árabe", "lasanha nota 2,1")
- [ ] **Code freeze às 23h**

### Qui 26/11 — manhã · Fechamento (até 12h)
- [ ] 09h00: rodar demo 3× do zero em máquina limpa; corrigir só o que quebra
- [ ] Gravar e editar vídeo de **≤3 min** (`docs/ROTEIRO-VIDEO.md`) + upload (YouTube não listado)
- [ ] README com "rodar em 5 comandos", screenshots, limitações e premissas
- [ ] Deploy Render/Streamlit + link no README + checklist final
- [ ] **11h00: submeter** (margem de 1h para o formulário)

---

## 7. Divisão de trabalho — time de 3 (decidido)

Com 3 pessoas, o escopo do MVP precisa ser **fechado**, não negociado durante a execução. O P1
inteiro não cabe: fica o que sustenta a narrativa (mesas + YOLO de fila) e sai o que é enfeite.

| Frente | Dono | Escopo travado |
|---|---|---|
| **A · IA + visão** | 1 pessoa | pipeline foto→JSON→CMV, fallback heurístico, pratos de demo, avaliação (MAPE), YOLO de fila |
| **B · Dados + back-end** | 1 pessoa | schema, seed, serviços, API, integração documentada, deploy, LGPD |
| **C · Produto + pitch** | 1 pessoa | 5 páginas, painel, alertas na tela, roteiro/vídeo, README, narrativa de negócio |

**O que cada um NÃO faz** (para não colidir):
- A não mexe em `app/`; B não mexe em `core/vision/`; C não mexe em `core/cmv.py`.
- `core/servico.py` é do B, mas C pode pedir campos novos — nunca editar por conta própria.
- Integração de branch: cada frente tem sua pasta; merges diários, um dono por arquivo.

**Checkpoints curtos (15 min, de pé):**
- Ter 24/11 23h — esqueleto rodando (`streamlit run` abre e navega)
- Qua 25/11 12h — DOR 1 fechada ponta a ponta
- Qua 25/11 20h — as 5 páginas com dados
- Qua 25/11 23h — **code freeze**
- Qui 26/11 09h — demo 3× em máquina limpa
- Qui 26/11 11h — submissão feita

**Prioridade em caso de atraso:** Balança → Painel → Feedback → Mesas → YOLO de fila.
Se o YOLO atrasar, o painel mostra a fila a partir dos eventos simulados e o vídeo anotado entra
como roadmap. Nunca cortar o CMV: é a dor nº 1 do cliente.

---

## 8. Caso de negócio (premissas explícitas — usar no pitch)

| Alavanca | Premissa | Impacto ilustrativo |
|---|---|---|
| Mix premium | 1 p.p. de mix a R$61/kg de diferença, prato de 550 g, 600 pratos/dia | **~R$ 205/dia** (~R$4,5 mil/mês) |
| Fila/desistência | 3% dos ~420 clientes do pico desistem; ticket R$80 | **~R$ 1,0 mil/dia** |
| Giro de mesa | 100 mesas no pico; 2 min a menos de latência; 5 lugares; dwell 37 min; ticket R$65 | **~R$ 1,7 mil/dia** |
| Desperdício | 5% de redução no resto com base em aceitação por item | depende do volume — apresentar como faixa |

Somar tudo é tentador, mas a banca premia quem **separa o que é medido do que é projetado**. Apresentar como "faixa de oportunidade identificada", não como retorno garantido — foi o próprio cliente que disse: *"não é uma promessa de retorno desse investimento"*.

**Investimento (BOM estimado, validar preços):**

| Item | Qtd | Unit. | Total |
|---|---|---|---|
| Câmera USB Full HD (ex. C920) | 3 | R$ 300 | R$ 900 |
| Suporte/braço articulado | 3 | R$ 80 | R$ 240 |
| Iluminação LED difusa | 3 | R$ 60 | R$ 180 |
| Mini PC (se não reusar o servidor local) | 1 | R$ 1.500 | R$ 1.500 |
| **Total** | | | **R$ 1.320 – 2.820** |

Alternativa "reuso do parque": câmera IP Intelbras (~R$ 400) via RTSP no NVR existente — melhor história de reuso, pior latência para o MVP. Documentar as duas.

---

## 9. Riscos e mitigações

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| VLM erra a composição | Alta | Alto | Normalização por densidade + confiança + chips de correção + métrica de MAPE honesta no pitch |
| Internet/API cai na demo | Média | Alto | Fallback OpenCV + fallback manual; SQLite local; vídeo gravado de backup |
| Sem vídeo de 1h30 para treinar/demonstrar fila | Média | Médio | Baixar um vídeo público de self-service para o protótipo + ROIs desenhados; deixar o pipeline plugável |
| Streamlit lento com muitas fotos | Média | Médio | Thumbnails 640px, cache `st.cache_data`, paginação |
| Supabase free tier estoura com fotos | Média | Baixo | Retenção 7 dias, WebP 640px, agregados em tabela separada |
| Escopo inflar (virar ERP) | Alta | Alto | Lista de "não construir" abaixo + code freeze quarta 23h |
| LGPD (imagens de pessoas) | Média | Médio | Sem reconhecimento facial, contagem agregada, câmera da balança só no prato, retenção curta, aviso na entrada |
| Time pequeno / poucas horas | Alta | Alto | Prioridade P0 fechada antes de qualquer P1; demo de 3 pratos sempre pronta |

### O que NÃO construir
Sem integração real com o JS Softcom · sem pagamento/caixa · sem cozinha/compras/estoque · sem fidelidade/CRM · sem app nativo · sem treinar YOLO de comida do zero · sem multi-loja · sem login complexo.

---

## 10. Definição de pronto (entrega)

- [ ] `git clone` + `pip install -r requirements.txt` + `streamlit run app/main.py` funciona em máquina limpa, **sem chave de API** (modo demo com pratos pré-analisados)
- [ ] Com a chave, o caminho real (foto → JSON → CMV) funciona
- [ ] 5 páginas navegáveis com dados sintéticos coerentes e rotulados
- [ ] `docs/`: arquitetura, planta de câmeras + BOM, integração A/B/C, LGPD, roteiro do vídeo, achados da palestra
- [ ] README com screenshots, premissas, limitações e roadmap
- [ ] Vídeo ≤3 min com link no README
- [ ] Tabela de avaliação do modelo (MAPE) — mesmo que o número não seja ótimo: **medir é o diferencial**
- [ ] Repositório **público**, link enviado no formulário até 11h

---

## 11. Backlog priorizado

**P0 (sem isso não há entrega):** captura+JSON+CMV · página Balança · Feedback 4 carinhas + Pergunta do Dia · Painel com CMV e mix×satisfação · comandas de demonstração · README + vídeo.

**P1 (diferenciais que cabem em 3 pessoas):** mesas com alerta · YOLO de fila no vídeo · reposições de cuba · drill-down da comanda.

**P2 (cortado do MVP):** estimativa de resto por área · mapa de calor do salão · conector real do JS Softcom · exportar CSV.

O **simulador de cenário** foi promovido para o P0 porque já está implementado no painel
(slider de mix premium → impacto em R$/dia e R$/mês): é o item de melhor relação
esforço/impacto no pitch. Um slider mostrando a margem mudar ao vivo vende melhor que
qualquer tabela.

---

## 12. Estado atual do repositório (scaffold entregue)

**Funcionando e testado (31 testes verdes):**

- [x] `core/cmv.py` — distribuição por densidade, custo, CMV, margem + testes
- [x] `core/vision/` — VLM (Gemini/OpenAI) + heurística OpenCV + fallback manual + cache
- [x] `core/demo.py` — 3 pratos sintéticos gerados na hora, com CMV esperado
- [x] `core/seed.py` — 3 dias de operação (540 comandas, pico 12h10–13h20, fila, cubas, mesas)
- [x] `core/fluxo.py` / `core/alertas.py` — Little, limiar de fila, prioridade de mesa, 6 regras de alerta
- [x] 5 páginas Streamlit + smoke test de abertura (`tests/test_app.py`) e de interação (`tests/test_fluxos.py`)
- [x] FastAPI com 10 rotas, incluindo webhook do SaaS, testado com `TestClient`
- [x] `scripts/verificar.py` (check de ambiente), `gerar_pratos_demo.py`, `avaliar_modelo.py`, `processar_video.py`
- [x] Docs: plano, achados, câmeras, integração, roteiro do vídeo, README do MVP

**Próximos passos (quinta, antes do freeze):**

1. Substituir as imagens sintéticas por 5–10 fotos reais de prato (o pipeline já aceita upload).
2. Rodar o protocolo de 20 pratos e colar o MAPE no README.
3. Gerar o vídeo anotado de fila com o vídeo de 1h30 (ou um trecho público) e colar o GIF no painel.
4. Promover `docs/README-MVP.md` para o `README.md` da raiz (hoje a raiz documenta o transcritor).
5. Deploy no Render + Streamlit Cloud e colar os links.
6. Gravar o vídeo de 3 min e colar o link no README.
