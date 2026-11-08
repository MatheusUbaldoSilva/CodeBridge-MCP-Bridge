"""IA Local: markdown simples do modelo -> HTML do Qt (titulos, negrito, listas, codigo)."""
from __future__ import annotations

import html
import re

CODE_FENCE = re.compile(r"```[^\n`]*\n?(.*?)(?:```|$)", re.S)
INLINE_CODE = re.compile(r"`([^`\n]+)`")
PRE_STYLE = ("background:#0a1015;border:1px solid #33414d;margin:6px 0;"
             "padding:6px;color:#dfe7ee;white-space:pre-wrap;")


def format_message(text: str) -> str:
    """Texto do modelo -> HTML simples: blocos ``` viram <pre>, `x` vira <code>."""
    out, last = [], 0
    for match in CODE_FENCE.finditer(text or ""):
        out.append(format_plain(text[last:match.start()].strip("\n")))
        out.append('<pre style="%s">%s</pre>'
                   % (PRE_STYLE, html.escape(match.group(1).strip("\n").rstrip())))
        last = match.end()
    out.append(format_plain((text or "")[last:].strip("\n")))
    return "".join(out)


HEADING = re.compile(r"^#{1,6}\s+(.*)$")
BULLET = re.compile(r"^(\s*)[-*]\s+(.*)$")
BOLD = re.compile(r"\*\*(.+?)\*\*")


def format_plain(text: str) -> str:
    """Markdown simples do modelo: titulos, **negrito**, listas e `codigo`."""
    lines = []
    for line in html.escape(text).split("\n"):
        heading = HEADING.match(line)
        if heading:
            line = '<b style="color:#dfe7ee;">%s</b>' % heading.group(1)
        else:
            bullet = BULLET.match(line)
            if bullet:
                line = "%s\u2022 %s" % ("&nbsp;" * 2 * len(bullet.group(1)), bullet.group(2))
        line = BOLD.sub(r"<b>\1</b>", line)
        lines.append(INLINE_CODE.sub(r'<code style="background:#0a1015;">\1</code>', line))
    return "<br>".join(lines)


# ---- saida de terminal com cores (ls --color, git, etc.) -------------------
# Codigos ANSI: o terminal SSH do CodeBridge mostra as cores; a conversa fazia
# aparecer "\x1b[01;34m". Aqui viram cores de verdade (e somem para o modelo).
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
SGR = re.compile(r"\x1b\[([0-9;]*)m")
ANSI_COLORS = {
    30: "#768390", 31: "#e5534b", 32: "#57ab5a", 33: "#c69026",
    34: "#539bf5", 35: "#b083f0", 36: "#39c5cf", 37: "#dfe7ee",
    90: "#8b98a5", 91: "#ff7b72", 92: "#7ee787", 93: "#f2cc60",
    94: "#79c0ff", 95: "#d2a8ff", 96: "#56d4dd", 97: "#ffffff",
}


def _clean_lines(text) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "")


def strip_ansi(text) -> str:
    """Texto do terminal sem codigos de cor/cursor (o que o modelo recebe)."""
    return ANSI_ESCAPE.sub("", _clean_lines(text))


def _apply_sgr(params: str, color):
    codes = [int(c) if c.isdigit() else 0 for c in params.split(";")] if params else [0]
    index = 0
    while index < len(codes):
        code = codes[index]
        if code in (0, 39):
            color = None
        elif code in ANSI_COLORS:
            color = ANSI_COLORS[code]
        elif code == 38 and index + 2 < len(codes) and codes[index + 1] == 5:
            n = codes[index + 2]
            color = ANSI_COLORS.get(30 + n if n < 8 else 82 + n) if n < 16 else None
            index += 2
        elif code == 38 and index + 4 < len(codes) and codes[index + 1] == 2:
            color = "#%02x%02x%02x" % tuple(min(255, v) for v in codes[index + 2:index + 5])
            index += 4
        index += 1
    return color


def ansi_to_html(text) -> str:
    """Saida de terminal -> HTML com as cores do ANSI; outros codigos somem."""
    text = _clean_lines(text)
    out, color, pos = [], None, 0

    def piece(chunk):
        chunk = html.escape(ANSI_ESCAPE.sub("", chunk))
        if chunk:
            out.append('<span style="color:%s;">%s</span>' % (color, chunk) if color else chunk)

    for match in SGR.finditer(text):
        piece(text[pos:match.start()])
        color = _apply_sgr(match.group(1), color)
        pos = match.end()
    piece(text[pos:])
    return "".join(out)


def output_block(text) -> str:
    """Bloco de codigo com a saida real do comando, nas cores do terminal."""
    body = _clean_lines(text).strip("\n").rstrip()
    return '<pre style="%s">%s</pre>' % (PRE_STYLE, ansi_to_html(body))
