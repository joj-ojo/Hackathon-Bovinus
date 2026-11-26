#!/usr/bin/env python
"""Benchmark rápido: transcreve os primeiros N segundos e mede velocidade/VRAM."""

from __future__ import annotations

import subprocess
import sys
import time

sys.path.insert(0, ".")
import transcrever  # noqa: E402  (adiciona DLLs CUDA)

from faster_whisper import WhisperModel  # noqa: E402

audio = sys.argv[1]
model_name = sys.argv[2] if len(sys.argv) > 2 else "medium"
seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 120.0

t0 = time.time()
try:
    model = WhisperModel(model_name, device="cuda", compute_type="int8_float16")
except Exception as exc:
    print(f"[erro] GPU falhou: {exc}")
    raise SystemExit(1)
carga = time.time() - t0

t1 = time.time()
segments, info = model.transcribe(
    audio,
    language="pt",
    beam_size=5,
    vad_filter=True,
    clip_timestamps=[0, seconds],
    condition_on_previous_text=False,
)
texto = " ".join(s.text.strip() for s in segments)
gasto = time.time() - t1

vram = subprocess.run(
    ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
    capture_output=True,
    text=True,
).stdout.strip()

print(f"modelo={model_name} carga={carga:.1f}s audio={seconds:.0f}s processado={gasto:.1f}s "
      f"RTF={gasto/seconds:.3f} (x{seconds/gasto:.1f} tempo real) VRAM={vram}")
print(f"texto ({len(texto.split())} palavras):\n{texto[:600]}")
