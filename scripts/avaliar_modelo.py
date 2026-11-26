"""Avaliação do modelo contra uma verdade conhecida.

Como usar:
1. Crie `data/avaliacao/` com pares `.json` + imagem.
2. Cada `.json` descreve o prato:
   {"foto": "prato_01.jpg", "peso_g": 612, "custo_kg_real": 31.20,
    "itens": {"carne_premium": 0.22, "acompanhamento": 0.48, "salada_legume": 0.30}}
3. Rode: python scripts/avaliar_modelo.py

O protocolo ideal no restaurante: compor 20 pratos pesando cada componente
separadamente na balança, fotografar e comparar. MAPE é a métrica do pitch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.cmv import calcular_cmv  # noqa: E402
from core.config import DATA_DIR  # noqa: E402
from core.vision import analisar_bytes  # noqa: E402

PASTA = DATA_DIR / "avaliacao"


def _mape(previsto: float, real: float) -> float:
    if real == 0:
        return 0.0 if previsto == 0 else 100.0
    return abs(previsto - real) / abs(real) * 100


def main(provider: str = "heuristica") -> int:
    if not PASTA.exists():
        print(f"Crie a pasta {PASTA} com as fotos e os .json de verdade conhecida.")
        print(__doc__)
        return 1

    casos = sorted(PASTA.glob("*.json"))
    if not casos:
        print("Nenhum caso de avaliação encontrado.")
        return 1

    erros_cmv: list[float] = []
    erros_categoria: dict[str, list[float]] = {}
    print(f"{'caso':<28}{'CMV real':>10}{'CMV prev':>10}{'erro':>8}")
    print("-" * 56)

    for arquivo in casos:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        foto = PASTA / dados["foto"]
        if not foto.exists():
            print(f"[!] foto ausente: {foto.name}")
            continue

        peso = float(dados["peso_g"])
        real = calcular_cmv(peso, [
            {"categoria": c, "percentual_area": p} for c, p in dados["itens"].items()
        ])

        previsto = analisar_bytes(foto.read_bytes(), peso, provider=provider)
        erro = _mape(previsto["cmv"]["cmv_pct"], real.cmv_pct)
        erros_cmv.append(erro)
        print(
            f"{arquivo.stem:<28}{real.cmv_pct:>9.1f}%{previsto['cmv']['cmv_pct']:>9.1f}%{erro:>7.1f}%"
        )

        detectado = {i["categoria"]: i["percentual_area"] for i in previsto["itens"]}
        for categoria, pct_real in dados["itens"].items():
            erros_categoria.setdefault(categoria, []).append(
                _mape(detectado.get(categoria, 0.0), pct_real)
            )

    if not erros_cmv:
        print("Nenhum caso válido.")
        return 1

    print("-" * 56)
    print(f"MAPE do CMV: {sum(erros_cmv) / len(erros_cmv):.1f}%  (n={len(erros_cmv)})")
    for categoria, valores in sorted(erros_categoria.items()):
        print(f"  {categoria:<20} MAPE área: {sum(valores) / len(valores):>5.1f}%")
    print("\nReporte este número no pitch, mesmo que não seja ótimo: medir é o diferencial.")
    return 0


if __name__ == "__main__":
    provedor = sys.argv[1] if len(sys.argv) > 1 else "heuristica"
    raise SystemExit(main(provedor))
