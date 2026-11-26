# Planta de câmeras e hardware

> Entregável arquitetural exigido no escopo: posicionamento das câmeras nas balanças e no salão.
> O objetivo é provar que a solução **reaproveita o parque Intelbras** e que o único gasto novo
> é pequeno e justificável.

## 1. Princípio

| Onde | Por que uma câmera ali | O que ela **não** faz |
|---|---|---|
| **Balança** | é o único ponto em que o prato está parado, iluminado e associado a um peso | não filma rosto, não identifica cliente |
| **Churrasqueira** | é o gargalo medido (4 min vs. meta de 2,5) | não avalia funcionário, só conta pessoas |
| **Entrada / escada** | é o ponto de desistência (fila visível da rua) | não reconhece quem passou |
| **Salão** | mede ocupação e tempo de mesa | não grava áudio, não faz reconhecimento facial |
| **Caixa** | fecha o ciclo de permanência | não lê tela de caixa nem cartão |

Regra de ouro: **a câmera da balança olha para baixo, para o prato.** Todo o resto é contagem
agregada de pessoas — nunca identificação.

## 2. Planta simplificada

```
                         ┌──────────────────────────────┐
                         │   SALÃO SUPERIOR (nível 2)    │
                         │   24–40 mesas · 4 garçons     │
                         │        [C5 ampla]             │
                         └──────────────┬───────────────┘
                                        │ escada interna
   ┌────────────────────────────────────┴───────────────────────────────┐
   │                       SALÃO PRINCIPAL (térreo)                     │
   │                                                                    │
   │   ┌──────────┐   ┌───────────────────────────┐   ┌─────────────┐   │
   │   │ BALANÇAS │   │        BUFFET             │   │ MESAS       │   │
   │   │  B1 B2 B3│   │ saladas → quentes →       │   │ [C4 ampla]  │   │
   │   │ [C1×3]   │   │ sobremesas → churrasqueira│   │             │   │
   │   └────┬─────┘   └────────────┬──────────────┘   └─────────────┘   │
   │        │                      │ [C2]                               │
   │        │               (fila da churrasqueira)                     │
   │   ┌────┴──────┐                                        ┌────────┐  │
   │   │ RECEPÇÃO  │                                        │ CAIXA  │  │
   │   │ [C3]      │                                        │ [C6]   │  │
   │   └────┬──────┘                                        └────────┘  │
   └────────┼───────────────────────────────────────────────────────────┘
            │  escada 5–6 degraus  ← ponto de desistência
        RUA AUGUSTA
```

## 3. Pontos de câmera

| ID | Local | Tipo | Altura / ângulo | O que mede | Prioridade |
|---|---|---|---|---|---|
| **C1** | Sobre cada balança (3 un.) | **nova** — USB Full HD ou IP Intelbras | 0,55–0,65 m, 90° (nadir), prato centralizado | composição do prato + nº da comanda no quadro | **P0** |
| **C2** | Churrasqueira | reuso Intelbras | 2,8–3,2 m, 30–40° | fila da churrasqueira (pessoas na ROI) | P1 |
| **C3** | Entrada / escada | reuso Intelbras | 2,8–3,0 m, 25–35° | fila na escada, fluxo de entrada | P1 |
| **C4** | Salão principal | reuso Intelbras | 3,0–3,5 m, 35–45° | ocupação de mesas (subconjunto) | P1 |
| **C5** | Salão superior | reuso Intelbras | 3,0–3,5 m, 35–45° | ocupação de mesas | P2 |
| **C6** | Caixa / saída | reuso Intelbras | 2,6–3,0 m, 30° | fila de pagamento | P2 |

O cliente confirmou em palestra que já existem câmeras Intelbras cobrindo **salão, cozinha e
financeiro**, com gravação local + Intelbras Cloud, e que **não há câmera focada na balança** —
mas que ela é "uma aquisição plausível" e de investimento pequeno.

## 4. Dimensionamento da câmera da balança

Câmera USB típica: 1920×1080, campo de visão horizontal ≈ 78°.

| Altura | Largura coberta | Prato de 26 cm ocupa | Resolução |
|---|---|---|---|
| 0,45 m | 0,73 m | 36% do quadro | ~2,6 px/mm |
| **0,55 m** | **0,89 m** | **29% do quadro** | **~2,1 px/mm** |
| 0,70 m | 1,13 m | 23% do quadro | ~1,7 px/mm |

**Recomendação: 0,55 m de altura, 90°.** O prato fica com ~500 px de diâmetro — folgado para
segmentação e para o VLM. Abaixo de 0,45 m a câmera atrapalha a operação; acima de 0,75 m a
área útil começa a ficar pequena.

Iluminação: anel de LED difuso 4000–5000 K, 10–15 W, em volta da lente. Evita sombra da mão do
operador e reflexo do aço da balança. **Sem luz dedicada, o CMV fica instável no fim da tarde.**

### Trigger de captura

Três opções, da melhor para a mais simples:

1. **Evento da balança** (ideal): peso estabilizado por 300 ms → dispara a foto.
2. **Barcode + peso** no agente de borda: o operador bipa a comanda, a balança envia o peso, o
   agente tira a foto.
3. **Pedal/botão** do operador (fallback manual, sempre disponível).

A foto deve sair **antes** de o cliente retirar o prato. Se a balança automática que eles estão
testando expuser um evento, o caminho 1 é direto.

## 5. Lista de materiais (BOM estimado)

| Item | Qtd | Unit. estimado | Total |
|---|---|---|---|
| Câmera USB Full HD com foco fixo (ex. Logitech C920/C270) | 3 | R$ 300 | R$ 900 |
| Braço/suporte articulado com fixação em bancada | 3 | R$ 80 | R$ 240 |
| Anel de LED difuso 4000–5000 K | 3 | R$ 60 | R$ 180 |
| Fonte/Extensora USB | 1 | R$ 90 | R$ 90 |
| Mini PC para inferência (se não reusar o servidor local) | 1 | R$ 1.500 | R$ 1.500 |
| **Total** | | | **R$ 1.320 – 2.820** |

**Alternativa "reuso total"**: 3 câmeras IP Intelbras (~R$ 400 cada) no NVR existente, via RTSP.
Custo parecido, ganho de padronização com o parque, perda de latência no MVP (snapshot RTSP é
mais lento que webcam USB). Documentar as duas e decidir com a TI do cliente.

## 6. Instalação — checklist

- [ ] Validar altura e ângulo com o prato real do buffet (não com um prato de casa)
- [ ] Fotografar 20 pratos com composição conhecida na posição final
- [ ] Confirmar que o número/código da comanda aparece no quadro (ou que o vínculo vem do bipe)
- [ ] Medir luminosidade em 3 horários (11h30, 12h45, 15h00) — a luz da rua muda
- [ ] Passar o cabo protegido (área de circulação de cliente e água)
- [ ] Fixar o foco e travar a exposição (autofoco é inimigo da segmentação)
- [ ] Desenhar as ROIs do salão sobre um frame de referência (`data/rois.json`)
- [ ] Treinar a equipe: o botão de correção de 2 segundos é parte do processo

### Calibração do CMV

1. Pesar separadamente cada componente de 20 pratos reais.
2. Fotografar na posição definitiva.
3. Rodar `python scripts/avaliar_modelo.py`.
4. Ajustar `core/custos.py` (custo/kg e densidade) até o MAPE estabilizar.
5. Reportar o MAPE — **não esconder**. É o número que dá credibilidade ao resto.

## 7. LGPD e privacidade

| Risco | Decisão |
|---|---|
| Reconhecimento facial | **não é feito**. Nenhum embedding, nenhuma identificação |
| Câmera na balança | enquadramento top-down no prato; rosto fora do quadro por construção |
| Contagem no salão | dado agregado por ROI (pessoas na região), sem vídeo individual |
| Retenção | fotos de prato: 7 dias · agregados: 90 dias · alertas: 30 dias |
| Base legal | legítimo interesse (operação e segurança), com aviso visual na entrada |
| Direitos do titular | não há dado pessoal identificável; mesmo assim, canal de contato no aviso |
| Fornecedor | Supabase com região definida; sem transferência de imagem para terceiros além do VLM contratado |
| Auditoria | log de quem acessou a foto (operação restrita ao gerente) |

> Se o cliente quiser usar as imagens para treinar modelo, isso precisa de base legal própria e
> anonimização — está fora do escopo do MVP e deve ser tratado antes de qualquer produção.
