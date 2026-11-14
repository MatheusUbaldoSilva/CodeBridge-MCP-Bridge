"""Ferramenta MCP para sincronizar pastas do servidor Linux para o Windows.

Fina camada sobre app_rewrite/project_sync.py: expoe add/remove/list/set_auto e
run/run_all/run_due. As acoes que mexem so na config nao abrem conexao; as
acoes run* abrem a sessao SSH salva no CodeBridge.

build_result e pura (recebe o 'engine' project_sync), para testar sem o pacote
mcp; register_project_sync_tools faz o import de mcp de forma preguicosa.
"""
import sys
from pathlib import Path
from typing import Any

_APP = Path(__file__).resolve().parent.parent / "app_rewrite"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))


def build_result(ps, action="list", **kw):
    action = (str(action) or "list").strip().lower()
    try:
        if action == "list":
            return {"operation_ok": True, "action": "list",
                    "pairs": ps.list_pairs()}
        if action == "add":
            if not kw.get("remote") or not kw.get("local"):
                return {"operation_ok": False, "action": "add",
                        "error_message": "remote e local sao obrigatorios"}
            pair = ps.add_pair(
                kw["remote"], kw["local"], project_id=kw.get("project_id"),
                interval_min=kw.get("interval_min") or 10,
                auto=bool(kw.get("auto")), index=bool(kw.get("index")),
                mirror=bool(kw.get("mirror")),
            )
            return {"operation_ok": True, "action": "add", "pair": pair}
        if action == "remove":
            ok = ps.remove_pair(kw.get("pair_id"))
            return {"operation_ok": ok, "action": "remove",
                    "pair_id": kw.get("pair_id")}
        if action == "set_auto":
            pair = ps.set_auto(kw.get("pair_id"), bool(kw.get("auto")))
            return {"operation_ok": pair is not None, "action": "set_auto",
                    "pair": pair}
        if action == "run":
            res = ps.sync_by_id(kw.get("pair_id"))
            if res is None:
                return {"operation_ok": False, "action": "run",
                        "error_message": "par nao encontrado: "
                        + str(kw.get("pair_id"))}
            return {"operation_ok": True, "action": "run", "result": res}
        if action == "run_all":
            res = ps.sync_pairs(ps.list_pairs())
            return {"operation_ok": True, "action": "run_all", "results": res}
        if action == "run_due":
            res = ps.run_due()
            return {"operation_ok": True, "action": "run_due", "results": res}
        return {"operation_ok": False, "action": action,
                "error_message": ("action invalida; use "
                                  "list|add|remove|set_auto|run|run_all|run_due")}
    except Exception as exc:
        return {"operation_ok": False, "action": action,
                "error_message": str(exc)}


def register_project_sync_tools(mcp, engine=None):
    from mcp.types import ToolAnnotations
    import project_sync as _default
    ps = engine if engine is not None else _default

    @mcp.tool(
        name="codebridge_project_sync",
        description=(
            "Sincroniza pastas do servidor Linux para o Windows por SFTP "
            "incremental (so o que mudou) e aditivo, deixando-as prontas para "
            "indexar no RAG. action: list (ver pares) | add (remote, local, "
            "project_id?, interval_min?, auto?) | remove (pair_id) | set_auto "
            "(pair_id, auto) | run (pair_id: sincroniza um) | run_all | run_due "
            "(os pares cujo intervalo ja passou). add/remove/set_auto so mexem na "
            "config; run* abrem a conexao SSH salva no painel do CodeBridge."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False, idempotent_hint=False, open_world_hint=True,
        ),
        structured_output=True,
    )
    def codebridge_project_sync(
        action: str = "list",
        pair_id: str | None = None,
        remote: str | None = None,
        local: str | None = None,
        project_id: str | None = None,
        interval_min: int | None = None,
        auto: bool = False,
        index: bool = False,
        mirror: bool = False,
    ) -> dict[str, Any]:
        return build_result(
            ps, action, pair_id=pair_id, remote=remote, local=local,
            project_id=project_id, interval_min=interval_min,
            auto=auto, index=index, mirror=mirror,
        )

    return codebridge_project_sync
