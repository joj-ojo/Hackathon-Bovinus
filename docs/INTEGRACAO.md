# Modelo de integração com o JS Softcom

> Entregável arquitetural exigido no escopo: integração via API/Webhooks com o sistema de caixa.
> A regra que governa tudo: **não invasiva**. O caixa, a recepção humanizada e o SaaS continuam
> funcionando exatamente como hoje.

## 1. O que se sabe do sistema atual

| Item | Fato (dito na palestra) | Implicação |
|---|---|---|
| Fornecedor | JS Softcom (caixa + atendimento) | produto de terceiro, sem documentação pública |
| Onde roda | **servidor local** na loja, com Wi-Fi para celulares dos garçons, balanças e caixas | há um ponto de rede interno aproveitável |
| Chave | **número da comanda** (4 dígitos, 1–9999) + código de barras no verso | é a nossa chave estrangeira natural |
| O que já registra | peso e valor por comanda, vários dias; fechamento com data/hora | fonte para conciliação e validação |
| O que não registra | composição do prato, fila, limpeza, resto, aceitação | é exatamente onde entramos |
| API | **desconhecida** ("não vou saber tecnicamente") | não podemos depender dela no MVP |

## 2. Três caminhos, com custo e dependência

| | A · Conector de borda ✅ | B · Espelho somente-leitura | C · API / Webhook |
|---|---|---|---|
| **Como** | agente local captura `(comanda, peso, foto)` no ato da pesagem | leitura do banco local ou export CSV do SaaS | eventos do SaaS para o nosso endpoint |
| **Depende de** | nada do fornecedor | acesso à TI/banco | contrato com o fornecedor |
| **Latência** | imediata | minutos/horas | imediata |
| **Cobre bebida** | não (só o que passa na balança) | sim | sim |
| **Risco** | baixo | baixo-médio | alto |
| **No MVP** | **implementado** | documentado | **contrato implementado e testado** |

**Decisão:** o MVP entrega A funcionando, C especificado e funcional (endpoint + testes) e B
como plano de enriquecimento. Isso mantém a solução vendável mesmo se o fornecedor nunca abrir
API — e é isso que torna o projeto "não invasivo" de verdade.

## 3. Caminho A — conector de borda

```
┌────────────┐   bipe    ┌──────────────┐   peso    ┌────────────────────┐
│  comanda   │──────────▶│   balança    │──────────▶│  agente local      │
└────────────┘           └──────────────┘           │  (Python)          │
                                                    │  1. recebe peso    │
      ┌────────────┐      foto (trigger)           │  2. dispara câmera │
      │  câmera C1 │───────────────────────────────▶│  3. analisa ou     │
      └────────────┘                                │     enfileira      │
                                                    │  4. grava no banco │
                                                    └─────────┬──────────┘
                                                              ▼
                                              Postgres/Supabase (ou SQLite local)
```

Pseudocódigo do laço (o mesmo que roda em `scripts/` no demo):

```python
while True:
    evento = balanca.aguardar_peso_estavel(timeout=30)   # (comanda, peso_g)
    if not evento:
        continue
    foto = camera.capturar()
    resultado = analisar_bytes(foto, evento.peso_g)      # VLM -> heurística -> manual
    with sessao() as s:
        servico.criar_comanda(s, numero=evento.comanda)
        persistir_pesagem(s, evento.comanda, resultado, foto_path=salvar_foto(foto))
    if resultado["status"] == "revisar":
        tela_operador.pedir_correcao(resultado)          # 2 segundos, humano no laço
```

Vantagens: zero dependência, funciona mesmo se o SaaS cair, e o dado nasce com foto e peso
juntos. Limitação: **não vê bebida** — que entra pelo caminho B ou C.

## 4. Caminho C — contrato de webhook (implementado)

`POST /webhooks/comanda` (ver `api/main.py`), autenticado por HMAC no header.

### Eventos

| Evento | Quando | Efeito no nosso lado |
|---|---|---|
| `comanda.aberta` | recepção entrega o cartão | cria a comanda (se não existir) |
| `item.lancado` | garçom lança bebida | soma `bebidas_valor` quando `payload.tipo == "bebida"` |
| `comanda.fechada` | pagamento no caixa/totem | grava `fechada_em` e `valor_pago` |

### Exemplos

```http
POST /webhooks/comanda
Content-Type: application/json
X-Assinatura: sha256=...

{"evento": "comanda.aberta", "comanda": "0421", "timestamp": "2026-11-26T12:14:03-03:00"}
```

```json
{
  "evento": "item.lancado",
  "comanda": "0421",
  "timestamp": "2026-11-26T12:19:41-03:00",
  "payload": { "tipo": "bebida", "item": "coca-cola lata", "quantidade": 1, "valor": 8.0 }
}
```

```json
{
  "evento": "comanda.fechada",
  "comanda": "0421",
  "timestamp": "2026-11-26T12:52:10-03:00",
  "payload": { "valor_pago": 78.13, "forma": "credito" }
}
```

### Regras de robustez (não negociáveis)

1. **Idempotência**: `(evento, comanda, timestamp)` é chave única. Reenvio não duplica.
2. **Retry com backoff**: 3 tentativas (2 s, 10 s, 60 s). Depois, fila morta + alerta.
3. **Autenticação**: HMAC-SHA256 do corpo com segredo compartilhado; rejeitar sem assinatura.
4. **Ordem**: aceitar fora de ordem (evento antigo não sobrescreve dado mais novo).
5. **Tempo**: `timestamp` com fuso explícito, sempre `-03:00`.
6. **Resposta**: `202 Accepted` rápido; processamento assíncrono.

## 5. Mapeamento de campos (a confirmar com a TI do cliente)

| Nosso campo | Provável origem no JS Softcom | Status |
|---|---|---|
| `comandas.numero` | número da comanda (4 dígitos) | ✅ confirmado |
| `comandas.codigo_barras` | código de barras impresso no verso | ✅ confirmado |
| `comandas.aberta_em` | abertura da comanda | ⚠️ confirmar formato |
| `pesagens.peso_g` | peso lançado pela balança | ✅ confirmado (existe no sistema) |
| `pesagens.preco_kg` | valor do quilo vigente | ⚠️ por dia/hora? |
| `comandas.bebidas_valor` | itens lançados pelos garçons | ⚠️ confirmar se vem por item |
| `comandas.fechada_em` | fechamento no caixa | ✅ confirmado (existe) |
| `comandas.pessoas` | não existe hoje | ❌ estimar (ou não usar) |
| `mesas.id` | não existe no SaaS | ❌ nosso domínio |

Nada disso bloqueia o MVP: o conector A preenche o essencial sozinho.

## 6. Sequência ponta a ponta

```
Cliente   Recepção    Balança   Agente    Nosso banco   Painel    SaaS
   │         │           │        │            │           │        │
   │─entra──▶│           │        │            │           │        │
   │         │─comanda──▶│        │            │           │        │
   │         │           │─peso──▶│            │           │        │
   │         │           │        │─foto+IA───▶│           │        │
   │         │           │        │            │─CMV/alerta▶│        │
   │─senta, garçom lança bebida─────────────────────────────────────▶│
   │         │           │        │            │◀──webhook item─────│
   │─feedback no totem─────────────────────────▶│           │        │
   │         │           │        │            │◀──webhook fechada──│
   │         │           │        │            │─fecha ciclo▶│        │
```

## 7. Rollout sugerido

| Fase | Duração | Escopo | Critério de saída |
|---|---|---|---|
| **Piloto** | 2 semanas | 1 balança, 1 câmera | MAPE de CMV medido; correções < 20% dos pratos |
| **Balanças** | 1 semana | 3 balanças | foto em > 95% das pesagens |
| **Salão** | 2 semanas | C2 e C3 (churrasqueira e escada) | alerta de fila com < 15% de falso positivo |
| **Mesas** | 2 semanas | C4 + botão do garçom | latência de higienização medida |
| **Integração C** | quando o fornecedor permitir | bebidas e fechamento | conciliação sem divergência |

## 8. Riscos de integração

| Risco | Mitigação |
|---|---|
| Fornecedor não abre API | caminho A já resolve o essencial; B como plano B |
| Atualização do SaaS quebra o conector | conector A não depende do SaaS; B é somente-leitura |
| Wi-Fi da loja instável | buffer local com fila em disco e reenvio |
| Dupla contagem de bebida | idempotência por chave de evento |
| Fuso horário errado no fechamento | exigir `timestamp` com offset; normalizar para America/Sao_Paulo |
| LGPD no envio de dados | só número de comanda, valores e horários; nenhum dado pessoal |
