"""Debug rápido do pipeline heurístico nos pratos de demonstração."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.demo import gerar_todas
from core.vision import analisar_bytes

for prato in gerar_todas():
    resultado = analisar_bytes(prato["caminho"].read_bytes(), prato["peso_g"], provider="heuristica")
    print(
        f"\n{prato['nome']}: esperado CMV {prato['cmv']['cmv_pct']:.1f}% | "
        f"detectado {resultado['cmv']['cmv_pct']:.1f}% | conf {resultado['confianca_global']:.2f}"
    )
    for item in resultado["itens"]:
        print(
            f"   {item['categoria']:<18} {item['percentual_area'] * 100:5.1f}%  "
            f"{item['peso_estimado_g']:4d} g"
        )
