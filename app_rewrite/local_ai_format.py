"""IA Local: markdown simples do modelo -> HTML do Qt (titulos, negrito, listas, codigo)."""
from __future__ import annotations

import html
import re

CODE_FENCE = re.compile(r"```[^\n`]*\n?(.*?)(?:```|$)", re.S)
INLINE_CODE = re.compile(r"`([^`\n]+)`")


def format_message(text: str) -> str:
    """Texto do modelo -> HTML simples: blocos ``` viram <pre>, `x` vira <code>."""
    out, last = [], 0
    for match in CODE_FENCE.finditer(text or ""):
        out.append(format_plain(text[last:match.start()].strip("\n")))
        out.append('<pre style="background:#0a1015;border:1px solid #33414d;margin:6px 0;'
                   'padding:6px;color:#dfe7ee;white-space:pre-wrap;">%s</pre>'
                   % html.escape(match.group(1).strip("\n").rstrip()))
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
