"""Contagem de pessoas por região de interesse em um vídeo (filas e mesas).

Usa YOLO11n pré-treinado (COCO) — não precisa de treino: detecta pessoas.
Depois aplica a Lei de Little para estimar espera por zona.

Uso:
    python scripts/processar_video.py --video midia/salao.mp4 --rois data/rois.json

Saídas:
    data/fila_processada.csv   (zona, segundo, pessoas, chegadas_por_min, espera_min)
    data/video_anotado.mp4     (vídeo com as caixas e as ROIs)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import DATA_DIR  # noqa: E402
from core.fluxo import espera_estimada  # noqa: E402


def carregar_rois(caminho: Path) -> dict[str, list[list[int]]]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return {zona: valor["poligono"] for zona, valor in dados.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--rois", type=Path, default=DATA_DIR / "rois.json")
    parser.add_argument("--modelo", default="yolo11n.pt")
    parser.add_argument("--passo", type=int, default=15, help="processa 1 a cada N frames")
    parser.add_argument("--conf", type=float, default=0.35)
    args = parser.parse_args()

    try:
        import cv2
        from ultralytics import YOLO
    except ImportError:
        print("Instale as dependências de IA: pip install -r requirements-ai.txt")
        return 1

    if not args.video.exists():
        print(f"Vídeo não encontrado: {args.video}")
        return 1
    if not args.rois.exists():
        print(f"ROIs não encontradas: {args.rois}")
        print("Use data/rois.example.json como modelo.")
        return 1

    rois = carregar_rois(args.rois)
    modelo = YOLO(args.modelo)
    captura = cv2.VideoCapture(str(args.video))
    fps = captura.get(cv2.CAP_PROP_FPS) or 25
    largura = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
    altura = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))

    saida_video = cv2.VideoWriter(
        str(DATA_DIR / "video_anotado.mp4"),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps / args.passo,
        (largura, altura),
    )

    linhas = []
    historico: dict[str, list[int]] = {zona: [] for zona in rois}
    frame_id = 0
    processados = 0

    while True:
        ok, frame = captura.read()
        if not ok:
            break
        frame_id += 1
        if frame_id % args.passo:
            continue

        resultado = modelo.predict(frame, classes=[0], conf=args.conf, verbose=False)[0]
        pontos = []
        for caixa in resultado.boxes.xyxy.cpu().numpy():
            x1, y1, x2, y2 = caixa
            pontos.append(((x1 + x2) / 2, y2))  # pé da pessoa: melhor para ROI de piso

        for zona, poligono in rois.items():
            contador = sum(
                1
                for px, py in pontos
                if cv2.pointPolygonTest(np.array(poligono, dtype=np.int32), (px, py), False) >= 0
            )
            historico[zona].append(contador)
            chegadas = 0.0
            if len(historico[zona]) > 10:
                # λ aproximado: novas pessoas por minuto na janela recente
                delta = max(0, historico[zona][-1] - historico[zona][-10])
                segundos = 10 * args.passo / fps
                chegadas = delta / segundos * 60 if segundos else 0.0
            linhas.append(
                {
                    "zona": zona,
                    "segundo": round(frame_id / fps, 1),
                    "pessoas": contador,
                    "chegadas_por_min": round(chegadas, 2),
                    "espera_min": round(espera_estimada(contador, chegadas), 2),
                }
            )

            cor = (0, 0, 200) if zona == "churrasqueira" else (200, 90, 0)
            cv2.polylines(frame, [np.array(poligono, dtype=np.int32)], True, cor, 2)
            cv2.putText(
                frame, f"{zona}: {contador}", (poligono[0][0] + 4, poligono[0][1] - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2,
            )

        for (px, py) in pontos:
            cv2.circle(frame, (int(px), int(py)), 4, (0, 220, 0), -1)

        saida_video.write(frame)
        processados += 1
        if processados % 100 == 0:
            print(f"{processados} frames processados…")

    captura.release()
    saida_video.release()

    destino = DATA_DIR / "fila_processada.csv"
    with destino.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)

    print(f"Pronto: {destino} ({len(linhas)} registros) e {DATA_DIR / 'video_anotado.mp4'}")
    print("Importe o CSV em data/ para alimentar a timeline do painel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
