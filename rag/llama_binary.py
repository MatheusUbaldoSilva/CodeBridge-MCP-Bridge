"""Uma copia so do llama-server para todas as IAs do CodeBridge.

Central RAG (Jina texto e codigo) e IA Local (Qwen) usam o mesmo executavel:
C:\\llama\\llama-server.exe, a versao que a RAG ja validou. A variavel
CODEBRIDGE_LLAMA_SERVER, se definida, aponta para outra copia.
"""
from __future__ import annotations

import os
from pathlib import Path

SHARED_LLAMA_SERVER = Path(r"C:\llama\llama-server.exe")
ENV_VAR = "CODEBRIDGE_LLAMA_SERVER"


def llama_server_path() -> Path:
    value = os.environ.get(ENV_VAR, "").strip()
    return Path(value) if value else SHARED_LLAMA_SERVER
