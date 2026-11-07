"""Textos do bloco de status do topo da janela (sem Qt, testavel).

Acentos e simbolos vem de chr() para o arquivo ficar so em ASCII.
"""
import html
import time

DOT = " " + chr(0xB7) + " "
ELLIPSIS = chr(0x2026)
_A = chr(0xE1)    # a agudo
_C = chr(0xE7)    # c cedilha
_ATIL = chr(0xE3)  # a til
_U = chr(0xFA)    # u agudo
_I = chr(0xED)    # i agudo

ACTIVE_TITLE = "Comando em execu" + _C + _ATIL + "o"
TUNNEL_TITLE = "T" + _U + "nel seguro"
MCP_TITLE = "Servidor MCP"

TERMINAL_NAMES = {
    "POWERSHELL5.1": "PowerShell 5.1",
    "POWERSHELL": "PowerShell 5.1",
    "CMD": "CMD",
    "SSH": "Linux (SSH)",
    "LINUX": "Linux (SSH)",
}

STATE_NAMES = {
    "CREATED": "preparando",
    "PREPARED": "preparado, aguardando",
    "QUEUED": "na fila",
    "PENDING": "na fila",
    "AWAITING_APPROVAL": "aguardando aprova" + _C + _ATIL + "o",
    "APPROVED": "aprovado",
    "RUNNING": "rodando",
    "EXECUTING": "rodando",
    "STOPPING": "parando",
    "CANCELLING": "parando",
    "FINISHED": "conclu" + _I + "do",
    "SUCCEEDED": "conclu" + _I + "do",
    "FAILED": "falhou",
    "CANCELLED": "cancelado",
}

OVERALL_NAMES = {"READY": "PRONTO", "DEGRADED": "COM PROBLEMAS"}


def terminal_name(target):
    key = str(target or "").strip().upper()
    return TERMINAL_NAMES.get(key, str(target or "?"))


def state_name(state):
    key = str(state or "").strip().upper()
    return STATE_NAMES.get(key, str(state or "").lower())


def overall_text(overall):
    value = str(overall or "").strip().upper()
    return "Estado geral: " + OVERALL_NAMES.get(value, value or "?")


def elapsed_text(seconds):
    seconds = max(0, int(seconds or 0))
    if seconds < 60:
        return f"h{_A} {seconds} s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"h{_A} {minutes} min {sec:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"h{_A} {hours} h {minutes:02d} min"


def command_preview(command, width=90):
    """Primeira linha util do comando, cortada, e quantas linhas sobram."""
    lines = [line.rstrip() for line in str(command or "").splitlines()]
    useful = [line for line in lines if line.strip()]
    if not useful:
        return "", 0
    first = useful[0].strip()
    if len(first) > width:
        first = first[: width - 1].rstrip() + ELLIPSIS
    elif len(useful) > 1:
        first = first + " " + ELLIPSIS
    return first, len(useful) - 1


def command_tooltip(command, max_lines=40, max_chars=4000):
    text = str(command or "")
    lines = text.splitlines()
    cut = "\n".join(lines[:max_lines])
    if len(cut) > max_chars:
        cut = cut[:max_chars]
    if len(lines) > max_lines or len(text) > len(cut):
        cut += "\n" + ELLIPSIS
    return cut


def service_text(title, state, pid=None, note=None, error=None):
    parts = [f"{title}: {state or 'OFFLINE'}"]
    if pid:
        parts.append(f"PID {pid}")
    if note:
        parts.append(note)
    text = DOT.join(parts)
    if error:
        text += DOT + "erro: " + str(error)
    return text


def api_text(online, host, port):
    return f"API local: {'ONLINE' if online else 'OFFLINE'}" + DOT + f"{host}:{port}"


def active_text(target=None, state=None, command=None, started_at=None,
                stop_requested=False, now=None, internal_id=None):
    """Devolve (rich_text, tooltip) da linha do comando em execucao."""
    if not target and not state:
        return f"{ACTIVE_TITLE}: nenhum", ""
    head = [terminal_name(target), state_name(state)]
    if started_at is not None:
        head[-1] += " " + elapsed_text((now or time.time()) - float(started_at))
    line1 = f"{ACTIVE_TITLE}: " + DOT.join(head)
    if stop_requested:
        line1 += DOT + "parada solicitada"
    preview, extra = command_preview(command)
    rich = html.escape(line1)
    if preview:
        more = f"  (+{extra} linhas)" if extra > 1 else ("  (+1 linha)" if extra == 1 else "")
        rich += ("<br><span style='color:#8a94a6; font-family: Consolas, monospace;'>"
                 + "&nbsp;&nbsp;" + html.escape(preview) + html.escape(more) + "</span>")
    tooltip = command_tooltip(command) if command else ""
    if internal_id:
        tooltip = (tooltip + "\n\n" if tooltip else "") + f"ID interno: {internal_id}"
    return rich, tooltip