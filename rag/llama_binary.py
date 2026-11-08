"""Uma copia so do llama-server para todas as IAs do CodeBridge.

Central RAG (Jina texto e codigo) e IA Local (Qwen) usam o mesmo executavel.
Ordem de busca:
  1. a variavel CODEBRIDGE_LLAMA_SERVER, se definida;
  2. %LOCALAPPDATA%\\CodeBridge\\llama\\llama-server.exe, onde o instalador das
     IAs (app_rewrite/ai_setup.py) coloca a versao certa para a maquina;
  3. C:\\llama\\llama-server.exe, a copia antiga que a RAG validou primeiro.
Se nenhuma existir, devolve o caminho 2 (o instalador das IAs cria).
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "CODEBRIDGE_LLAMA_SERVER"
LLAMA_BUILD = 10819  # versao do llama.cpp validada pela RAG e baixada pelo instalador
USER_LLAMA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "CodeBridge" / "llama"
LEGACY_LLAMA_SERVER = Path(r"C:\llama\llama-server.exe")
SHARED_LLAMA_SERVER = LEGACY_LLAMA_SERVER  # nome antigo, mantido por compatibilidade


def user_llama_server() -> Path:
    return USER_LLAMA_DIR / "llama-server.exe"


def llama_server_path() -> Path:
    value = os.environ.get(ENV_VAR, "").strip()
    if value:
        return Path(value)
    for candidate in (user_llama_server(), LEGACY_LLAMA_SERVER):
        if candidate.is_file():
            return candidate
    return user_llama_server()
