"""Gera as 5 capturas de tela da solução em docs/img/ (usadas no README).

Uso (na raiz do repositório):
    pip install -r requirements.txt -r requirements-dev.txt
    python -m playwright install chromium
    python scripts/capturar_telas.py

Sobe o Streamlit numa porta própria, tira os prints e encerra o servidor.
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "docs" / "img"
PORTA = 8599
BASE = f"http://localhost:{PORTA}"


def esperar_servidor(timeout: int = 120) -> None:
    limite = time.time() + timeout
    while time.time() < limite:
        try:
            with urllib.request.urlopen(f"{BASE}/_stcore/health", timeout=2) as resp:
                if resp.read().strip() == b"ok":
                    return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("O Streamlit não subiu a tempo.")


def abrir(pagina, rota: str, largura: int, altura: int, espera: float = 4.0) -> None:
    pagina.set_viewport_size({"width": largura, "height": altura})
    pagina.goto(f"{BASE}/{rota}", wait_until="domcontentloaded")
    pagina.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=60_000)
    time.sleep(espera)  # deixa gráficos e tabelas terminarem de renderizar


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    servidor = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app/main.py",
         "--server.headless", "true", "--server.port", str(PORTA),
         "--browser.gatherUsageStats", "false"],
        cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        esperar_servidor()
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            pagina = navegador.new_page()

            # 1) Balança: prato de demonstração analisado
            abrir(pagina, "Balanca", 1440, 1100, espera=3)
            pagina.get_by_text("Prato de demonstração", exact=True).click()
            time.sleep(2)
            pagina.get_by_role("button", name="Analisar prato").click()
            time.sleep(6)
            pagina.screenshot(path=str(SAIDA / "01-balanca.png"))

            # 2) Painel gerencial (viewport alto para caber mais gráficos)
            abrir(pagina, "Painel", 1440, 1900, espera=6)
            pagina.screenshot(path=str(SAIDA / "02-painel.png"))

            # 3) Mesas
            abrir(pagina, "Mesas", 1440, 1100)
            pagina.screenshot(path=str(SAIDA / "03-mesas.png"))

            # 4) Feedback, em tamanho de celular
            abrir(pagina, "Feedback", 430, 1100)
            pagina.screenshot(path=str(SAIDA / "04-feedback-mobile.png"))

            # 5) Comandas
            abrir(pagina, "Comandas", 1440, 1100)
            pagina.screenshot(path=str(SAIDA / "05-comandas.png"))

            navegador.close()
        print(f"Prints salvos em {SAIDA}")
    finally:
        servidor.terminate()


if __name__ == "__main__":
    main()
