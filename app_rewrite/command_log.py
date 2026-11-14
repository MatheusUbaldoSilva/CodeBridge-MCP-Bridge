"""Registro diario dos comandos executados pelo CodeBridge.

Um arquivo por dia em %LOCALAPPDATA%\\CodeBridge\\command-log\\commands-AAAA-MM-DD.jsonl
(JSON Lines: uma linha por comando). Gravado na hora em que o job termina, sem
loop. Guarda o comando COMPLETO, porem com segredos mascarados (--api-key,
senhas, tokens, credenciais em URL). Nao guarda projeto.

Enganchado em JobStore.finish(), que recebe o registro do job ja pronto.
Desligar: variavel de ambiente CODEBRIDGE_COMMAND_LOG=0.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

ENABLED_ENV = "CODEBRIDGE_COMMAND_LOG"   # "0"/"off"/"false" desliga
LOG_OUTPUT = True                        # grava um resumo curto da saida
OUTPUT_SUMMARY_CHARS = 400               # tamanho maximo desse resumo
MASK = "****"

_LOCK = threading.Lock()
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# target do executor -> tipo curto no log
_TYPES = {
    "POWERSHELL5.1": "powershell",
    "POWERSHELL": "powershell",
    "CMD": "cmd",
    "SSH": "ssh",
}

# --- redacao de segredos (sem segredos no log) ----------------------------
# valor de flags sensiveis: --api-key X | --api-key=X | --password "x" ...
_FLAG = re.compile(
    r"(?i)(--?(?:api[-_]?key|password|passwd|pwd|token|secret|auth[-_]?token|bearer)"
    r"[=\s]+)(\"[^\"]*\"|'[^']*'|\S+)"
)
# chave=valor / chave: valor  (password=..., token: ..., api_key=...)
_KV = re.compile(
    r"(?i)\b(api[-_]?key|password|passwd|pwd|token|secret|access[-_]?token)"
    r"(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)
# cabecalho Authorization: Bearer/Basic xxxxx
_AUTH = re.compile(r"(?i)(authorization\s*:?\s*(?:bearer|basic)\s+)(\S+)")
# credenciais em URL: scheme://user:senha@host -> scheme://user:****@host
_URLCRED = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://[^\s:/@]+:)([^\s@/]+)(@)")


def redact(text) -> str:
    """Mascara segredos mantendo o resto do comando/saida intactos."""
    if not text:
        return ""
    text = str(text)
    text = _FLAG.sub(lambda m: m.group(1) + MASK, text)
    text = _KV.sub(lambda m: m.group(1) + m.group(2) + MASK, text)
    text = _AUTH.sub(lambda m: m.group(1) + MASK, text)
    text = _URLCRED.sub(lambda m: m.group(1) + MASK + m.group(3), text)
    return text


def strip_ansi(text) -> str:
    return _ANSI.sub("", str(text or ""))


# --- caminhos -------------------------------------------------------------
def log_dir(root=None) -> Path:
    base = Path(root) if root else Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "CodeBridge" / "command-log"


def day_file(when=None, root=None) -> Path:
    when = when or datetime.now().astimezone()
    return log_dir(root) / ("commands-%s.jsonl" % when.strftime("%Y-%m-%d"))


# --- montagem da linha ----------------------------------------------------
def _type_for(target) -> str:
    key = str(target or "").upper()
    return _TYPES.get(key, key.lower() or "?")


def _local_dt(job) -> datetime:
    """Horario local (fuso da maquina) do termino do comando."""
    raw = job.get("finished_at") or job.get("created_at")
    try:
        dt = datetime.fromisoformat(raw)
        return dt.astimezone() if dt.tzinfo else dt
    except (TypeError, ValueError):
        return datetime.now().astimezone()


def _duration_ms(job):
    start = job.get("started_at") or job.get("created_at")
    end = job.get("finished_at")
    try:
        return max(0, int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() * 1000))
    except (TypeError, ValueError):
        return None


def summarize_output(output) -> str:
    text = redact(strip_ansi(output)).strip()
    if len(text) <= OUTPUT_SUMMARY_CHARS:
        return text
    head = OUTPUT_SUMMARY_CHARS - 120
    return text[:head].rstrip() + " [...] " + text[-100:].lstrip()


def build_entry(job, when=None) -> dict:
    when = when or _local_dt(job)
    entry = {
        "ts": when.isoformat(timespec="seconds"),
        "tipo": _type_for(job.get("target")),
        "estado": job.get("state"),
        "exit": job.get("exit_code"),
        "ms": _duration_ms(job),
        "comando": redact(job.get("command")),  # comando completo, sem segredos
    }
    if LOG_OUTPUT:
        entry["saida"] = summarize_output(job.get("output"))
    erro = job.get("error_message")
    if erro:
        entry["erro"] = redact(erro)
    return entry


def enabled() -> bool:
    return str(os.environ.get(ENABLED_ENV, "")).strip().lower() not in ("0", "off", "false", "no")


def record(job, root=None) -> bool:
    """Acrescenta uma linha ao log do dia. Nunca levanta excecao."""
    if not enabled() or not isinstance(job, dict) or not job.get("command"):
        return False
    try:
        when = _local_dt(job)
        line = json.dumps(build_entry(job, when), ensure_ascii=False) + "\n"
        path = day_file(when=when, root=root)
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
        return True
    except Exception:
        return False
