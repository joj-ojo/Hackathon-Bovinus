#!/usr/bin/env python
r"""
Transcrição local com faster-whisper.

Uso:
  .venv\\Scripts\\python transcrever.py "midia\palestra.webm"
  .venv\\Scripts\\python transcrever.py "midia\palestra.webm" --model large-v3 --lang pt

Saídas (em .\\transcricoes\\<nome>): .txt, .srt, .vtt, .json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import site
import sys
import time
from pathlib import Path


def add_nvidia_dll_dirs() -> list[str]:
    """No Windows, os wheels nvidia-*-cu12 trazem cublas/cudnn fora do PATH."""
    if os.name != "nt":
        return []
    candidates: list[str] = []
    roots = list(site.getsitepackages())
    if hasattr(site, "getusersitepackages"):
        roots.append(site.getusersitepackages())
    for root in roots:
        for pattern in ("nvidia/*/bin", "nvidia/*/lib"):
            candidates.extend(glob.glob(os.path.join(root, pattern)))
    added = []
    for path in candidates:
        if not os.path.isdir(path):
            continue
        try:
            os.add_dll_directory(path)
            os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
            added.append(path)
        except OSError:
            pass
    return added


ADDED_DLLS = add_nvidia_dll_dirs()

from faster_whisper import WhisperModel  # noqa: E402


def fmt_ts(seconds: float, sep: str = ".") -> str:
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def fmt_srt_ts(seconds: float) -> str:
    return fmt_ts(seconds, ",")


def write_outputs(base: Path, segments, text: str, meta: dict) -> None:
    txt_path = base.with_suffix(".txt")
    txt_path.write_text(text.strip() + "\n", encoding="utf-8")

    with base.with_suffix(".srt").open("w", encoding="utf-8") as fh:
        for i, seg in enumerate(segments, 1):
            fh.write(f"{i}\n{fmt_srt_ts(seg.start)} --> {fmt_srt_ts(seg.end)}\n{seg.text.strip()}\n\n")

    with base.with_suffix(".vtt").open("w", encoding="utf-8") as fh:
        fh.write("WEBVTT\n\n")
        for seg in segments:
            fh.write(f"{fmt_ts(seg.start)} --> {fmt_ts(seg.end)}\n{seg.text.strip()}\n\n")

    payload = {
        **meta,
        "segments": [
            {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()}
            for s in segments
        ],
    }
    base.with_suffix(".json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcreve audio/video localmente com faster-whisper")
    ap.add_argument("input", help="arquivo de audio ou video")
    ap.add_argument("--model", default="large-v3", help="tiny|base|small|medium|large-v3 (default: large-v3)")
    ap.add_argument("--lang", default=None, help="idioma, ex: pt (default: detectar)")
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"], help="default: cuda (cai para cpu se falhar)")
    ap.add_argument("--compute-type", default=None, help="default: int8_float16 na GPU, int8 na CPU")
    ap.add_argument("--beam-size", type=int, default=5)
    ap.add_argument("--out-dir", default="transcricoes")
    ap.add_argument("--vad", action="store_true", default=True, help="filtro de silêncio (default: ligado)")
    ap.add_argument("--no-vad", dest="vad", action="store_false")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"[erro] arquivo não encontrado: {src}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / src.stem

    compute_type = args.compute_type or ("int8_float16" if args.device == "cuda" else "int8")

    # Ordem de tentativas: GPU com o modelo pedido, GPU com modelo menor (4 GB VRAM), CPU.
    attempts: list[tuple[str, str, str]] = [(args.device, args.model, compute_type)]
    if args.device == "cuda" and args.model not in ("tiny", "base", "small"):
        attempts.append(("cuda", "medium", "int8_float16"))
        attempts.append(("cuda", "small", "int8_float16"))
    attempts.append(("cpu", args.model, "int8"))

    device, model_name, model = None, None, None
    for dev, name, ctype in attempts:
        try:
            print(f"[info] carregando modelo {name} ({dev}/{ctype})...", flush=True)
            model = WhisperModel(name, device=dev, compute_type=ctype)
            device, model_name = dev, name
            break
        except Exception as exc:  # GPU indisponível / VRAM insuficiente / sem rede
            print(f"[aviso] falhou {name}/{dev}: {type(exc).__name__}: {exc}", file=sys.stderr)
    if model is None:
        print("[erro] não foi possível carregar nenhum modelo", file=sys.stderr)
        return 1

    print(f"[info] transcrevendo {src.name} ...", flush=True)
    started = time.time()
    segments_iter, info = model.transcribe(
        str(src),
        language=args.lang,
        beam_size=args.beam_size,
        vad_filter=args.vad,
        vad_parameters={"min_silence_duration_ms": 700},
        condition_on_previous_text=False,
    )
    total = info.duration or 0
    segments = []
    last_report = 0.0
    for seg in segments_iter:
        segments.append(seg)
        if seg.end - last_report >= 15 or seg.end >= total:
            last_report = seg.end
            pct = (seg.end / total * 100) if total else 0
            print(
                f"  {fmt_ts(seg.end)} / {fmt_ts(total)} ({pct:5.1f}%)  {seg.text.strip()[:70]}",
                flush=True,
            )

    text = " ".join(s.text.strip() for s in segments)
    meta = {
        "source": str(src),
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
        "language": getattr(info, "language", args.lang),
        "duration_seconds": round(total, 2),
        "elapsed_seconds": round(time.time() - started, 1),
    }
    write_outputs(base, segments, text, meta)

    print(f"\n[ok] {len(segments)} segmentos em {meta['elapsed_seconds']}s")
    print(f"[ok] arquivos: {base}.txt | .srt | .vtt | .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
