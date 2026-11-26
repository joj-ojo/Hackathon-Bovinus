# Protocolo de avaliação do modelo (20 pratos)

Esta pasta é onde a **verdade conhecida** entra. Sem ela, o CMV é opinião.

## Como rodar o experimento no restaurante (30 minutos)

1. Separe 20 pratos reais do buffet, cobrindo os perfis da casa:
   - 5 com predomínio de carne premium (picanha, filé)
   - 5 equilibrados
   - 5 com predomínio de carboidrato (arroz/feijão/massa)
   - 5 com predomínio de salada
2. Monte cada prato e **pese cada componente separadamente** na balança da loja.
   Anote o peso de cada categoria.
3. Fotografe cada prato na posição definitiva da câmera (altura e luz reais).
4. Some os pesos: esse é o `peso_g` que a balança veria.
5. Preencha um `.json` por prato, no formato abaixo.
6. Rode:

```powershell
python scripts/avaliar_modelo.py heuristica   # modo offline
python scripts/avaliar_modelo.py auto         # com VLM, se houver chave
```

## Formato do arquivo

`prato_01.json`:

```json
{
  "foto": "prato_01.jpg",
  "peso_g": 612,
  "itens": {
    "carne_premium": 0.22,
    "carne_media": 0.08,
    "acompanhamento": 0.41,
    "salada_legume": 0.24,
    "sobremesa": 0.05
  }
}
```

- `itens` são as **proporções de peso** (não de área) medidas na balança. O script converte
  para o CMV real e compara com o previsto.
- Use as mesmas categorias de `core/custos.py`.

## O que reportar no pitch

- **MAPE do CMV** (erro percentual médio absoluto) — o número que resume tudo.
- MAPE por categoria (mostra onde o modelo erra mais).
- Taxa de pratos com `status: revisar` (quantos precisaram de correção humana).

Um MAPE de 15–25% já é suficiente para decisão de gestão de mix. **Diga o número real.**
Esconder o erro é o jeito mais rápido de perder a confiança da banca e do cliente.
