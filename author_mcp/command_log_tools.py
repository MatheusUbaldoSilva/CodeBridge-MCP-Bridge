"""Ferramenta MCP somente-leitura do log diario de comandos do CodeBridge.

Expoe codebridge_command_log, que le os arquivos JSONL gravados pelo app
(app_rewrite/command_log.py) em %LOCALAPPDATA%\\CodeBridge\\command-log\\.
Nao executa comandos nem altera nada. Registrada no mcp_server.py.
"""
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# command_log.py vive em app_rewrite, irmao de author_mcp no diretorio de instalacao.
_APP = Path(__file__).resolve().parent.parent / "app_rewrite"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))


def _today() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def build_result(cl, action="day", day=None, limit=None) -> dict:
    """Monta a resposta da ferramenta. 'cl' e o modulo command_log (injetavel em teste)."""
    action = (str(action) or "day").strip().lower()
    if action == "list":
        return {"operation_ok": True, "action": "list", "days": cl.available_days()}
    if action != "day":
        return {"operation_ok": False, "action": action, "days": [], "entries": [],
                "error_message": "action invalida; use 'day' ou 'list'"}
    entries = cl.read_day(day)
    if isinstance(limit, int) and limit > 0:
        entries = entries[-limit:]
    return {
        "operation_ok": True,
        "action": "day",
        "day": day or _today(),
        "summary": cl.summarize_day(entries),
        "entries": entries,
        "rendered": cl.render_day(entries),
    }


def register_command_log_tools(mcp, reader=None):
    from mcp.types import ToolAnnotations
    import command_log as _default
    cl = reader if reader is not None else _default

    @mcp.tool(
        name="codebridge_command_log",
        description=(
            "Consulta somente leitura do log diario de comandos executados pelo "
            "CodeBridge (um arquivo por dia; segredos ja mascarados). Use para "
            "responder 'o que fiz no dia X / quais comandos rodaram'. Nao executa "
            "comandos nem altera nada. action='day' (padrao), com 'day' opcional no "
            "formato AAAA-MM-DD, retorna o resumo e a lista do dia; action='list' "
            "retorna os dias que tem log."
        ),
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True,
                                    open_world_hint=False),
        structured_output=True,
    )
    def codebridge_command_log(
        action: str = "day", day: str | None = None, limit: int | None = None,
    ) -> dict[str, Any]:
        return build_result(cl, action, day, limit)

    return codebridge_command_log
