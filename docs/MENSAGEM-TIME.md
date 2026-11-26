# Mensagem para o time

Pessoal, o projeto está no GitHub e **já roda de ponta a ponta** com dados de demonstração. Não é mockup: é código rodando.

🔗 **https://github.com/ThiagoDantas19/hackathon-fmu-2026-bovinos**

## Como ver (Windows)

```powershell
git clone https://github.com/ThiagoDantas19/hackathon-fmu-2026-bovinos
cd hackathon-fmu-2026-bovinos
.\run.ps1
```

Abre em `http://localhost:8501`. Cria a venv, instala tudo, gera os dados de exemplo e sobe o painel. Não precisa de chave de API nem de internet.

Se não tiver o `run.ps1` (Linux/Mac): `pip install -r requirements.txt` e `streamlit run app/main.py`.

## O que está pronto

- **Balança (foto → peso por alimento → CMV)**: sobe a foto do prato, identifica os alimentos, divide o peso por densidade (churrasco pesa mais que salada) e calcula o custo real daquela comanda. Com chave de IA usa visão de modelo; sem chave cai num classificador OpenCV offline — a demo nunca trava.
- **Painel do gestor**: CMV e margem por dia, espera p95 na fila, mesas sujas, nota por prato e alertas priorizados (ex.: lasanha 2,05/4, churrasqueira 4,7 min).
- **Fila e mesas**: contagem de pessoas por câmera (YOLO pré-treinado, sem treinar modelo próprio) → espera e ocupação.
- **API FastAPI** com `POST /webhooks/comanda`, pronta para o conector da balança.
- **Dados**: SQLite no demo, Postgres/Supabase só trocando `DATABASE_URL`; mesmo `core/` no painel e na API.
- **31 testes passando** (validei clonando o repo do zero), verificação de ambiente e 3 dias de dados semeados.

## O que falta (já dividido)

- **Balança/Vision**: trocar os 3 pratos sintéticos por 8–10 fotos reais e rodar o protocolo de 20 pratos para publicar o MAPE medido.
- **Painel/Front**: polir as telas e gravar o vídeo de 3 min.
- **Infra/Integração**: vídeo anotado da fila e deploy (Render/Streamlit Cloud).

## Decisões travadas (para não retrabalhar)

1. Não mexemos no PDV nem no caixa — número da comanda é a chave única.
2. Nada de treinar modelo de comida em 48h: IA genérica + heurística + fallback manual.
3. Escopo só nos 4 problemas: mix/CMV, fila, mesa, qualidade/desperdício. Cardápio, compras, estoque e fidelidade estão fora.

Documentação completa em `docs/` — comecem por `PLANO-TECNICO.md` e pelo `README.md` da raiz.
