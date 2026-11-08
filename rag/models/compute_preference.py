"""Chave global de processamento das IAs do CodeBridge: AUTO, GPU ou CPU.

Escolhida no card "IAs" do topo da janela e gravada em
%LOCALAPPDATA%\\CodeBridge\\ai\\compute.json. A Central RAG le aqui antes de ligar
um modelo e a IA Local le o mesmo arquivo. A variavel CODEBRIDGE_AI_COMPUTE,
se definida, vale mais que o arquivo.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

COMPUTE_MODES = ("AUTO", "GPU", "CPU")
DEFAULT_COMPUTE = "AUTO"
ENV_VAR = "CODEBRIDGE_AI_COMPUTE"


def preference_file() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "CodeBridge" / "ai" / "compute.json"


def normalize(value) -> str:
    value = str(value or "").strip().upper()
    return value if value in COMPUTE_MODES else DEFAULT_COMPUTE


def load_compute(path=None) -> str:
    env = os.environ.get(ENV_VAR)
    if env:
        return normalize(env)
    try:
        data = json.loads(Path(path or preference_file()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_COMPUTE
    return normalize(data.get("compute") if isinstance(data, dict) else None)


def save_compute(mode, path=None) -> str:
    mode = str(mode or "").strip().upper()
    if mode not in COMPUTE_MODES:
        raise ValueError("modo de processamento invalido: " + str(mode))
    path = Path(path or preference_file())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"compute": mode}) + "\n", encoding="utf-8")
    return mode
