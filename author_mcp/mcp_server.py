import argparse
import base64
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import Icon, ToolAnnotations
from pydantic import BaseModel

from http_client import ProtocolHTTPClient


class PingResult(BaseModel):
    status: str
    mensagem: str
    desafio: str
    executor_conectado: bool
    timestamp_utc: str
    turn_control: dict[str, Any] | None = None


class ProtocolOutcome(BaseModel):
    operation_ok: bool = True
    operation_error_type: str | None = None
    operation_error_message: str | None = None
    turn_control: dict[str, Any] | None = None


class StatusResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    app: str | None
    version: str | None
    overall: str | None
    api_online: bool
    terminals: dict[str, Any]
    queue: dict[str, Any] | None
    executor: dict[str, Any] | None
    auto_execute: bool
    completion_sound: dict[str, Any] | None


class PrepareResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    state: str
    target: str
    command_hash: str
    prepared_at: str | None
    duplicate: bool
    enter_sent: bool


class DiscardResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    discarded: bool
    prepared_request_id: str | None
    reason: str | None = None


class TerminalDispatchResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    mode: str
    auto_execute: bool
    preview_seconds: float
    prepared: dict[str, Any]
    execution: dict[str, Any] | None


class AsyncStartResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    mode: str
    auto_execute: bool
    preview_seconds: float
    prepared: dict[str, Any]
    execution: dict[str, Any] | None


class ExecutionStatusResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    execution: dict[str, Any]


class V2ExecutionEnvelope(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    execution: dict[str, Any]


class V2ExecutionStopResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    stop: dict[str, Any]


class V2OutputResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    output: dict[str, Any]


class ExecResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    state: str
    runtime_state: str
    execution_id: str
    target: str
    exit_code: int | None
    duration_ms: int | None
    started_at: str | None
    finished_at: str | None
    output: str
    stdout: str
    stderr: str
    stream_mode: str
    streams_separated: bool
    error_source: str | None
    error_type: str | None
    error_message: str | None
    raw_available: bool
    cursor: int
    complete: bool
    output_mode: str
    wait_timeout_ms: int


class WaitResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    state: str
    runtime_state: str
    execution_id: str
    target: str
    exit_code: int | None
    duration_ms: int | None
    started_at: str | None
    finished_at: str | None
    stdout: str
    stderr: str
    stream_mode: str
    streams_separated: bool
    error_source: str | None
    error_type: str | None
    error_message: str | None
    cursor: int
    next_cursor: int
    text: str
    chars: int
    available_chars: int
    has_more: bool
    eof: bool
    complete: bool
    timed_out: bool
    raw_available: bool
    wait_timeout_ms: int


class StopResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    cancelled: bool


class ExecuteResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    prepared_request_id: str
    state: str
    target: str
    command_hash: str
    started_at: str | None
    finished_at: str | None
    output: str
    exit_code: int | None
    error_type: str | None
    error_message: str | None
    duplicate: bool
    enter_sent: bool


def _server_icons():
    icon_path = (
        Path(__file__).resolve().parent.parent
        / "assets"
        / "codebridge_mcp_64.png"
    )
    try:
        encoded = base64.b64encode(icon_path.read_bytes()).decode("ascii")
    except OSError:
        return []
    return [
        Icon(
            src="data:image/png;base64," + encoded,
            mime_type="image/png",
            sizes=["64x64"],
        )
    ]


mcp = MCPServer(
    name="CodeBridge Autoral",
    title="CodeBridge MCP Bridge",
    description="MCP autoral do CodeBridge. Terminal visivel, execucao assincrona e retorno persistente.",
    icons=_server_icons(),
    version="0.8.0",
)


def _outcome_fields(payload):
    return {
        "operation_ok": bool(payload.get("operation_ok", True)),
        "operation_error_type": payload.get("error_type"),
        "operation_error_message": payload.get("error_message"),
        "turn_control": payload.get("turn_control"),
    }


def _duration_ms(started_at, finished_at):
    if not started_at or not finished_at:
        return None
    try:
        start = datetime.fromisoformat(str(started_at))
        finish = datetime.fromisoformat(str(finished_at))
    except (TypeError, ValueError):
        return None
    return max(0, int(round((finish - start).total_seconds() * 1000)))


def _error_source(error_type):
    if not error_type:
        return None
    name = str(error_type).strip().lower()
    if "command" in name or "cancel" in name:
        return "command"
    if "session" in name or "terminal" in name or "shell" in name:
        return "shell"
    if "protocol" in name or "http" in name or "mcp" in name:
        return "mcp"
    return "executor"


def _stream_contract(output):
    return {
        "stdout": str(output or ""),
        "stderr": "",
        "stream_mode": "COMBINED",
        "streams_separated": False,
    }


def _exec_result(exchange, payload, *, target, output_mode, wait_timeout_ms):
    runtime_state = str(payload.get("state") or "ERROR")
    complete = runtime_state in {"FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"}
    state = "RUNNING" if runtime_state in {"CREATED", "RUNNING"} else runtime_state
    terminal_output = (payload.get("output") or "") if complete else ""
    error_type = payload.get("error_type") if complete else None
    return ExecResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        state=state,
        runtime_state=runtime_state,
        execution_id=str(payload.get("execution_id") or ""),
        target=str(payload.get("target") or target or ""),
        exit_code=payload.get("exit_code") if complete else None,
        duration_ms=_duration_ms(
            payload.get("started_at"),
            payload.get("finished_at"),
        ),
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        output=terminal_output,
        **_stream_contract(terminal_output),
        error_source=_error_source(error_type),
        error_type=error_type,
        error_message=payload.get("error_message") if complete else None,
        raw_available=bool(payload.get("execution_id")),
        cursor=0,
        complete=complete,
        output_mode=output_mode,
        wait_timeout_ms=wait_timeout_ms,
    )


@mcp.tool(
    name="codebridge_ping",
    description="Diagnostico simples do MCP autoral sem acessar terminais.",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    structured_output=True,
)
def codebridge_ping(desafio: str) -> PingResult:
    turn_control = None
    try:
        exchange = ProtocolHTTPClient().exchange(
            "STATUS",
            {},
        )
        turn_control = (
            exchange.get("payload") or {}
        ).get("turn_control")
    except Exception:
        pass

    return PingResult(
        status="ok",
        mensagem="CODEBRIDGE_AUTHOR_OK",
        desafio=desafio,
        executor_conectado=False,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        turn_control=turn_control,
    )


@mcp.tool(
    name="codebridge_status",
    description="Consulta somente leitura do estado atual do CodeBridge via handshake CBMCP/1.",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    structured_output=True,
)
def codebridge_status() -> StatusResult:
    exchange = ProtocolHTTPClient().exchange("STATUS", {})
    payload = exchange["payload"]
    return StatusResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        app=payload.get("app"),
        version=payload.get("version"),
        overall=payload.get("overall"),
        api_online=bool(payload.get("api_online")),
        terminals=payload.get("terminals") or {},
        queue=payload.get("queue"),
        executor=payload.get("executor"),
        auto_execute=bool(payload.get("auto_execute")),
        completion_sound=payload.get(
            "completion_sound"
        ),
    )



@mcp.tool(
    name="codebridge_prepare",
    description="Prepara um comando no terminal real do CodeBridge sem enviar Enter.",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
    structured_output=True,
)
def codebridge_prepare(target: str, command: str) -> PrepareResult:
    exchange = ProtocolHTTPClient().exchange(
        "PREPARE", {"target": target, "command": command}
    )
    payload = exchange["payload"]
    return PrepareResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        state=str(payload.get("state") or "ERROR"),
        target=str(payload.get("target") or ""),
        command_hash=str(payload.get("command_hash") or ""),
        prepared_at=payload.get("prepared_at"),
        duplicate=bool(payload.get("duplicate")),
        enter_sent=bool(payload.get("enter_sent")),
    )


@mcp.tool(
    name="codebridge_terminal",
    description="Envia target + comando ao terminal real. Respeita o Auto do CodeBridge: OFF prepara sem Enter; ON prepara, exibe e executa.",
    annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=True,
        idempotent_hint=True, open_world_hint=True,
    ),
    structured_output=True,
)
def codebridge_terminal(target: str, command: str) -> TerminalDispatchResult:
    exchange = ProtocolHTTPClient(timeout=135.0).exchange(
        "DISPATCH", {"target": target, "command": command}
    )
    payload = exchange["payload"]
    return TerminalDispatchResult(
        protocol="CBMCP/1", handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        mode=str(payload.get("mode") or "ERROR"),
        auto_execute=bool(payload.get("auto_execute")),
        preview_seconds=float(payload.get("preview_seconds") or 0.0),
        prepared=payload.get("prepared") or {},
        execution=payload.get("execution"),
    )


@mcp.tool(
    name="codebridge_execute_prepared",
    description="Envia Enter uma unica vez para o comando preparado e retorna o resultado.",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=True,
        open_world_hint=True,
    ),
    structured_output=True,
)
def codebridge_execute_prepared(prepared_request_id: str) -> ExecuteResult:
    exchange = ProtocolHTTPClient(timeout=130.0).exchange(
        "EXECUTE_PREPARED", {"prepared_request_id": prepared_request_id}
    )
    payload = exchange["payload"]
    return ExecuteResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        prepared_request_id=str(payload.get("prepared_request_id") or ""),
        state=str(payload.get("state") or "ERROR"),
        target=str(payload.get("target") or ""),
        command_hash=str(payload.get("command_hash") or ""),
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        output=payload.get("output") or "",
        exit_code=payload.get("exit_code"),
        error_type=payload.get("error_type"),
        error_message=payload.get("error_message"),
        duplicate=bool(payload.get("duplicate")),
        enter_sent=bool(payload.get("enter_sent")),
    )


@mcp.tool(
    name="codebridge_discard",
    description="Descarta o comando atualmente preparado sem enviar Enter.",
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def codebridge_discard(request_id: str | None = None) -> DiscardResult:
    exchange = ProtocolHTTPClient().exchange("DISCARD", {"request_id": request_id})
    payload = exchange["payload"]
    return DiscardResult(protocol="CBMCP/1", handshake_confirmed=True, request_id=exchange["request_syn"]["request_id"], response_id=exchange["response_syn"]["response_id"], **_outcome_fields(payload), discarded=bool(payload.get("discarded")), prepared_request_id=payload.get("request_id"), reason=payload.get("reason"))


@mcp.tool(
    name="codebridge_start",
    description="Inicia execucao assincrona no terminal real. AUTO OFF apenas prepara; AUTO ON retorna rapidamente e executa em background.",
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True),
    structured_output=True,
)
def codebridge_start(target: str, command: str) -> AsyncStartResult:
    exchange = ProtocolHTTPClient(timeout=12.0).exchange(
        "START_ASYNC", {"target": target, "command": command}
    )
    payload = exchange["payload"]
    return AsyncStartResult(
        protocol="CBMCP/1", handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        mode=str(payload.get("mode") or "ERROR"),
        auto_execute=bool(payload.get("auto_execute")),
        preview_seconds=float(payload.get("preview_seconds") or 0.0),
        prepared=payload.get("prepared") or {},
        execution=payload.get("execution"),
    )


@mcp.tool(
    name="codebridge_execution_status",
    description="Consulta estado e novos trechos de saida de uma execucao sem reenviar o comando.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def codebridge_execution_status(execution_id: str, cursor: int = 0, max_chars: int = 65536) -> ExecutionStatusResult:
    exchange = ProtocolHTTPClient(timeout=10.0).exchange(
        "EXECUTION_STATUS", {"execution_id": execution_id, "cursor": cursor, "max_chars": max_chars}
    )
    payload = exchange["payload"]
    return ExecutionStatusResult(
        protocol="CBMCP/1", handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        execution=payload if payload.get("operation_ok", True) else {},
    )


@mcp.tool(
    name="codebridge_exec",
    description="Executa pelo caminho v2 e aguarda por uma janela curta. Retorna resultado final se concluir ou RUNNING com execution_id sem reenviar o comando.",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=False,
        open_world_hint=True,
    ),
    structured_output=True,
)
def codebridge_exec(
    target: str,
    command: str,
    wait_timeout_ms: int = 1500,
    output_mode: str = "NORMAL",
) -> ExecResult:
    wait_timeout_ms = max(0, min(int(wait_timeout_ms or 0), 10000))
    output_mode = str(output_mode or "NORMAL").strip().upper()
    if output_mode != "NORMAL":
        raise ValueError(
            "MCP-PROD-001 suporta apenas output_mode=NORMAL; COMPACT/RAW entram em MCP-PROD-004"
        )

    start_exchange = ProtocolHTTPClient(timeout=12.0).exchange(
        "EXECUTION_V2_START",
        {"target": target, "command": command},
    )
    start_payload = start_exchange["payload"]
    if not start_payload.get("operation_ok", True):
        return _exec_result(
            start_exchange,
            start_payload,
            target=target,
            output_mode=output_mode,
            wait_timeout_ms=wait_timeout_ms,
        )

    execution_id = str(start_payload.get("execution_id") or "")
    if not execution_id:
        return _exec_result(
            start_exchange,
            start_payload,
            target=target,
            output_mode=output_mode,
            wait_timeout_ms=wait_timeout_ms,
        )

    deadline = time.monotonic() + (wait_timeout_ms / 1000.0)
    last_exchange = start_exchange
    last_payload = start_payload

    while True:
        state = str(last_payload.get("state") or "")
        if state in {"FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"}:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return _exec_result(
                last_exchange,
                last_payload,
                target=target,
                output_mode=output_mode,
                wait_timeout_ms=wait_timeout_ms,
             )
        time.sleep(min(0.05, remaining))
        last_exchange = ProtocolHTTPClient(timeout=10.0).exchange(
            "EXECUTION_V2_STATUS",
            {"execution_id": execution_id},
         )
        last_payload = last_exchange["payload"]

    result_exchange = ProtocolHTTPClient(timeout=10.0).exchange(
        "EXECUTION_V2_RESULT",
        {"execution_id": execution_id},
    )
    result_payload = result_exchange["payload"]
    status_payload = last_payload
    merged = dict(status_payload)
    merged.update(result_payload)
    merged.setdefault("target", start_payload.get("target") or target)
    merged.setdefault("started_at", status_payload.get("started_at"))
    merged.setdefault("finished_at", status_payload.get("finished_at"))
    merged.setdefault("execution_id", execution_id)
    return _exec_result(
        result_exchange,
        merged,
        target=target,
        output_mode=output_mode,
        wait_timeout_ms=wait_timeout_ms,
    )


@mcp.tool(
    name="codebridge_wait",
    description="Aguarda output novo ou estado terminal de uma execucao existente sem reenviar o comando. Usa cursor incremental e retorna por output, conclusao ou timeout.",
    annotations=ToolAnnotations(
        read_only_hint=True,
        idempotent_hint=True,
        open_world_hint=False,
    ),
    structured_output=True,
)
def codebridge_wait(
    execution_id: str,
    cursor: int = 0,
    wait_timeout_ms: int = 15000,
    max_chars: int = 32768,
) -> WaitResult:
    execution_id = str(execution_id or "").strip()
    if not execution_id:
        raise ValueError("execution_id obrigatorio")

    cursor = max(0, int(cursor or 0))
    wait_timeout_ms = max(0, min(int(wait_timeout_ms or 0), 120000))
    max_chars = max(1, min(int(max_chars or 32768), 262144))
    deadline = time.monotonic() + (wait_timeout_ms / 1000.0)
    terminal_states = {"FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"}

    while True:
        output_exchange = ProtocolHTTPClient(timeout=10.0).exchange(
            "EXECUTION_V2_OUTPUT",
            {
                "execution_id": execution_id,
                "cursor": cursor,
                "max_chars": max_chars,
            },
        )
        output_payload = output_exchange["payload"]

        if not output_payload.get("operation_ok", True):
            return WaitResult(
                protocol="CBMCP/1",
                handshake_confirmed=True,
                request_id=output_exchange["request_syn"]["request_id"],
                response_id=output_exchange["response_syn"]["response_id"],
                **_outcome_fields(output_payload),
                state="ERROR",
                runtime_state=str(output_payload.get("state") or "ERROR"),
                execution_id=execution_id,
                target=str(output_payload.get("target") or ""),
                exit_code=None,
                duration_ms=None,
                started_at=output_payload.get("started_at"),
                finished_at=output_payload.get("finished_at"),
                **_stream_contract(""),
                error_source="mcp",
                error_type=output_payload.get("error_type"),
                error_message=output_payload.get("error_message"),
                cursor=cursor,
                next_cursor=cursor,
                text="",
                chars=0,
                available_chars=0,
                has_more=False,
                eof=False,
                complete=False,
                timed_out=False,
                raw_available=False,
                wait_timeout_ms=wait_timeout_ms,
            )

        runtime_state = str(output_payload.get("state") or "RUNNING")
        state = "RUNNING" if runtime_state in {"CREATED", "RUNNING"} else runtime_state
        text = str(output_payload.get("text") or "")
        next_cursor = int(output_payload.get("next_cursor", cursor) or cursor)
        complete = bool(output_payload.get("complete")) or runtime_state in terminal_states
        has_more = bool(output_payload.get("has_more"))
        eof = bool(output_payload.get("eof"))

        result_payload = {}
        result_exchange = output_exchange
        if complete:
            result_exchange = ProtocolHTTPClient(timeout=10.0).exchange(
                "EXECUTION_V2_RESULT",
                {"execution_id": execution_id},
            )
            result_payload = result_exchange["payload"]
            if result_payload.get("operation_ok", True):
                runtime_state = str(result_payload.get("state") or runtime_state)
                state = "RUNNING" if runtime_state in {"CREATED", "RUNNING"} else runtime_state

        if text or has_more or complete:
            structured_output = (result_payload.get("output") or "") if complete else ""
            structured_error_type = result_payload.get("error_type") if complete else None
            return WaitResult(
                protocol="CBMCP/1",
                handshake_confirmed=True,
                request_id=result_exchange["request_syn"]["request_id"],
                response_id=result_exchange["response_syn"]["response_id"],
                **_outcome_fields(result_payload or output_payload),
                state=state,
                runtime_state=runtime_state,
                execution_id=execution_id,
                target=str(result_payload.get("target") or output_payload.get("target") or ""),
                exit_code=result_payload.get("exit_code") if complete else None,
                duration_ms=_duration_ms(
                    result_payload.get("started_at") or output_payload.get("started_at"),
                    result_payload.get("finished_at") or output_payload.get("finished_at"),
                ) if complete else None,
                started_at=result_payload.get("started_at") or output_payload.get("started_at"),
                finished_at=result_payload.get("finished_at") or output_payload.get("finished_at"),
                **_stream_contract(structured_output),
                error_source=_error_source(structured_error_type),
                error_type=structured_error_type,
                error_message=result_payload.get("error_message") if complete else None,
                cursor=cursor,
                next_cursor=next_cursor,
                text=text,
                chars=int(output_payload.get("chars", len(text)) or 0),
                available_chars=int(output_payload.get("available_chars", len(text)) or 0),
                has_more=has_more,
                eof=eof,
                complete=complete,
                timed_out=False,
                raw_available=True,
                wait_timeout_ms=wait_timeout_ms,
            )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return WaitResult(
                protocol="CBMCP/1",
                handshake_confirmed=True,
                request_id=output_exchange["request_syn"]["request_id"],
                response_id=output_exchange["response_syn"]["response_id"],
                **_outcome_fields(output_payload),
                state=state,
                runtime_state=runtime_state,
                execution_id=execution_id,
                target=str(output_payload.get("target") or ""),
                exit_code=None,
                duration_ms=None,
                started_at=output_payload.get("started_at"),
                finished_at=output_payload.get("finished_at"),
                **_stream_contract(""),
                error_source=None,
                error_type=None,
                error_message=None,
                cursor=cursor,
                next_cursor=next_cursor,
                text="",
                chars=0,
                available_chars=int(output_payload.get("available_chars", 0) or 0),
                has_more=False,
                eof=eof,
                complete=False,
                timed_out=True,
                raw_available=True,
                wait_timeout_ms=wait_timeout_ms,
            )

        time.sleep(min(0.10, remaining))


@mcp.tool(
    name="codebridge_v2_start",
    description="Inicia execucao assincrona persistente em PowerShell 5.1, CMD ou SSH e retorna execution_id rapidamente.",
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True),
    structured_output=True,
)
def codebridge_v2_start(target: str, command: str) -> V2ExecutionEnvelope:
    exchange = ProtocolHTTPClient(timeout=12.0).exchange(
        "EXECUTION_V2_START", {"target": target, "command": command}
    )
    payload = exchange["payload"]
    return V2ExecutionEnvelope(
        protocol="CBMCP/1", handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        execution=payload if payload.get("operation_ok", True) else {},
    )


@mcp.tool(
    name="codebridge_v2_status",
    description="Consulta estado persistente pelo execution_id sem reenviar o comando.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def codebridge_v2_status(execution_id: str) -> V2ExecutionEnvelope:
    exchange = ProtocolHTTPClient(timeout=10.0).exchange(
        "EXECUTION_V2_STATUS", {"execution_id": execution_id}
    )
    payload = exchange["payload"]
    return V2ExecutionEnvelope(
        protocol="CBMCP/1", handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        execution=payload if payload.get("operation_ok", True) else {},
    )


@mcp.tool(
    name="codebridge_v2_result",
    description="Retorna resultado persistido quando a execucao atingir estado terminal.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def codebridge_v2_result(execution_id: str) -> V2ExecutionEnvelope:
    exchange = ProtocolHTTPClient(timeout=10.0).exchange(
        "EXECUTION_V2_RESULT", {"execution_id": execution_id}
    )
    payload = exchange["payload"]
    return V2ExecutionEnvelope(
        protocol="CBMCP/1", handshake_confirmed=True,

        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        execution=payload if payload.get("operation_ok", True) else {},
    )


@mcp.tool(
    name="codebridge_v2_output",
    description="Le a saida persistida em blocos por cursor, sem reenviar o comando.",
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def codebridge_v2_output(execution_id: str, cursor: int = 0, max_chars: int = 32768) -> V2OutputResult:
    exchange = ProtocolHTTPClient(timeout=10.0).exchange(
        "EXECUTION_V2_OUTPUT",
        {"execution_id": execution_id, "cursor": cursor, "max_chars": max_chars},
    )
    payload = exchange["payload"]
    return V2OutputResult(
        protocol="CBMCP/1", handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        output=payload if payload.get("operation_ok", True) else {},
    )


@mcp.tool(
    name="codebridge_v2_stop",
    description="Cancela somente a execucao identificada pelo execution_id.",
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def codebridge_v2_stop(execution_id: str) -> V2ExecutionStopResult:
    exchange = ProtocolHTTPClient(timeout=10.0).exchange(
        "EXECUTION_V2_STOP", {"execution_id": execution_id}
    )
    payload = exchange["payload"]
    return V2ExecutionStopResult(
        protocol="CBMCP/1", handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        stop=payload if payload.get("operation_ok", True) else {},
    )


@mcp.tool(
    name="codebridge_stop",
    description="Interrompe com Ctrl+C a execucao ativa ou descarta um comando apenas preparado.",
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False),
    structured_output=True,
)
def codebridge_stop() -> StopResult:
    exchange = ProtocolHTTPClient().exchange("STOP", {})
    payload = exchange["payload"]
    return StopResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        cancelled=bool(payload.get("cancelled")),
    )


def build_security(port: int) -> TransportSecuritySettings:
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[f"127.0.0.1:{port}", f"localhost:{port}"],
        allowed_origins=[
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        ],
    )




def main():
    parser = argparse.ArgumentParser(description="CodeBridge MCP autoral")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    security = build_security(args.port)
    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path="/mcp",
        transport_security=security,
    )




if __name__ == "__main__":
    main()
