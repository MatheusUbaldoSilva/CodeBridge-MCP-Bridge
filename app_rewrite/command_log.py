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


# --- leitura / resumo do log ---------------------------------------------
def available_days(root=None) -> list:
    """Datas (AAAA-MM-DD) que tem arquivo de log, da mais antiga a mais recente."""
    directory = log_dir(root)
    try:
        return sorted(p.stem.replace("commands-", "") for p in directory.glob("commands-*.jsonl"))
    except OSError:
        return []


def read_day(day=None, root=None) -> list:
    """Registros do dia (um dict por comando); ignora linhas invalidas."""
    if day is None:
        day = datetime.now().astimezone().strftime("%Y-%m-%d")
    path = log_dir(root) / ("commands-%s.jsonl" % day)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


def _hhmm(ts) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%H:%M")
    except (TypeError, ValueError):
        return "--:--"


def render_day(entries) -> str:
    """Lista cronologica legivel dos comandos (para 'quais comandos rodaram')."""
    linhas = []
    for e in entries:
        exit_code = e.get("exit")
        if exit_code == 0:
            marca = "ok"
        elif exit_code not in (None, 0):
            marca = "x(%s)" % exit_code
        else:
            marca = (e.get("estado") or "?").lower()
        ms = e.get("ms")
        dur = ((" %.1fs" % (ms / 1000)).replace(".", ",")) if isinstance(ms, int) else ""
        linhas.append("%s [%s] %s%s: %s" % (
            _hhmm(e.get("ts")), e.get("tipo", "?"), marca, dur, e.get("comando", "")))
    return "\n".join(linhas)


def summarize_day(entries) -> dict:
    """Contagens do dia: total, por tipo, falhas e janela de horario."""
    from collections import Counter
    tipos = Counter(e.get("tipo", "?") for e in entries)
    falhas = sum(1 for e in entries if e.get("exit") not in (None, 0))
    horas = [_hhmm(e.get("ts")) for e in entries if e.get("ts")]
    return {
        "total": len(entries),
        "por_tipo": dict(tipos),
        "falhas": falhas,
        "primeiro": horas[0] if horas else None,
        "ultimo": horas[-1] if horas else None,
    }


def _main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Le o log diario de comandos do CodeBridge.")
    parser.add_argument("--day", help="AAAA-MM-DD (padrao: hoje)")
    parser.add_argument("--list", action="store_true", help="lista os dias com log")
    parser.add_argument("--summary", action="store_true", help="so o resumo do dia")
    parser.add_argument("--root", help="base alternativa (uso interno/testes)")
    args = parser.parse_args(argv)
    if args.list:
        days = available_days(args.root)
        print("\n".join(days) if days else "(nenhum dia com log)")
        return 0
    day = args.day or datetime.now().astimezone().strftime("%Y-%m-%d")
    entries = read_day(day, args.root)
    resumo = summarize_day(entries)
    print("Dia %s: %d comando(s), %d falha(s), tipos %s"
          % (day, resumo["total"], resumo["falhas"], resumo["por_tipo"] or "{}"))
    if resumo["primeiro"]:
        print("Janela: %s - %s" % (resumo["primeiro"], resumo["ultimo"]))
    if not args.summary and entries:
        print("-" * 40)
        print(render_day(entries))
    return 0


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(_main())
