"""Register checkpoint tools without changing the live timer or executor."""
from typing import Any
from mcp.types import ToolAnnotations
from development_checkpoint import DevelopmentCheckpoints
from runtime_client import codebridge_turn_control


def register_development_checkpoint_tools(mcp, store=None, control_reader=None):
    storage = store if store is not None else DevelopmentCheckpoints()
    read_control = control_reader if control_reader is not None else codebridge_turn_control

    @mcp.tool(
        name="codebridge_dev_checkpoint_save",
        description="Salva progresso compacto do desenvolvimento, vinculado a sessao ativa do CodeBridge. Nao inclua segredos.",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                    idempotent_hint=False, open_world_hint=False),
        structured_output=True,
    )
    def codebridge_dev_checkpoint_save(
        summary: str, next_step: str, completed: list[str] | None = None,
        pending: list[str] | None = None,
    ) -> dict[str, Any]:
        control = read_control()
        stage = control.get("stage")
        if (not control.get("claimed_by_codebridge")
                or stage not in ("NORMAL", "PREPARE_WRAP_UP", "WRAP_UP_NOW")):
            raise RuntimeError("no claimed active CodeBridge session")
        checkpoint = storage.save(
            control.get("request_id"), summary, next_step, completed, pending,
            stage="RUNNING" if stage == "NORMAL" else stage,
        )
        return {"state": "CHECKPOINT_SAVED", "checkpoint": checkpoint,
                "turn_control": control}

    @mcp.tool(
        name="codebridge_dev_checkpoint_latest",
        description="Recupera o ultimo checkpoint de desenvolvimento do CodeBridge sem executar comandos.",
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True,
                                    open_world_hint=False),
        structured_output=True,
    )
    def codebridge_dev_checkpoint_latest(
        session_id: str | None = None,
    ) -> dict[str, Any]:
        checkpoint = storage.latest(session_id)
        return {"state": "CHECKPOINT_FOUND" if checkpoint else "NO_CHECKPOINT",
                "checkpoint": checkpoint}

    return codebridge_dev_checkpoint_save, codebridge_dev_checkpoint_latest
