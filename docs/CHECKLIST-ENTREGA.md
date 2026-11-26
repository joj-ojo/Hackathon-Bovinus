# Checklist de entrega · Hackathon FMU 2026

Prazo: **quinta, 26/11, às 12h**. Um repositório por grupo, enviado pelo líder no formulário.

## Antes de enviar

- [ ] **Repositório público** (Settings → General → Danger Zone → Change visibility). Abrir em aba anônima para confirmar.
- [ ] Repositório continua público durante todo o período de avaliação.
- [ ] `README.md` com resumo, prints, link do vídeo e link dos slides, sem nenhum `COLE_AQUI` restante.
- [ ] **5 prints** em `docs/img/` (rode `python scripts/capturar_telas.py`). No máximo 5.
- [ ] **Vídeo ≤ 2:00** publicado e com link funcionando em aba anônima.
- [ ] **Slides ≤ 5** exportados para `docs/apresentacao/Bovinus-Inteligencia-Operacional-5-slides.pdf`.
- [ ] `.env` não foi commitado (está no `.gitignore`) e nenhuma chave de API aparece no histórico.
- [ ] `pytest -q` e `python scripts/verificar.py` passando em um clone novo.
- [ ] Decidir se a pasta `transcricoes/` e `docs/MENSAGEM-TIME.md` ficam públicas (contêm a fala de terceiros e mensagens internas do time).

## Mapa dos requisitos

| Requisito | Onde está |
|---|---|
| Detalhamento e desenvolvimento | [`docs/DETALHAMENTO.md`](DETALHAMENTO.md), [`docs/PLANO-TECNICO.md`](PLANO-TECNICO.md) |
| Problema e solução | seções "O problema" e "A solução" do [`README.md`](../README.md) |
| Capturas de tela (máx. 5) | `docs/img/` |
| Vídeo (máx. 2 min) | link no README e arquivo em `docs/video/` |
| Slides (máx. 5) | `docs/apresentacao/` |
| Diagramas, código, banco, sistema | [`docs/DIAGRAMAS.md`](DIAGRAMAS.md), `app/`, `core/`, `api/`, `core/seed.py` |
