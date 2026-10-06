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


class CapabilitiesResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    app: str | None
    version: str | None
    targets: list[str]
    features: dict[str, bool]
    limits: dict[str, Any]
    preferred_tools: list[str]
    legacy_tools: list[dict[str, Any]]
    migration: dict[str, Any]


class ReadOnlyBatchResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    count: int
    ok_count: int
    error_count: int
    complete: bool
    read_only: bool
    parallel: bool
    workers_used: int
    max_workers: int
    items: list[dict[str, Any]]


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
    failed_command: str | None
    shell_alive: bool | None
    execution_recoverable: bool
    raw_available: bool
    cursor: int
    complete: bool
    requested_output_mode: str
    output_mode: str
    compaction_applied: bool
    stdout_lines: int
    stderr_lines: int
    stdout_chars: int
    stderr_chars: int
    returned_stdout_chars: int
    important_sections: list[str]
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
    failed_command: str | None
    shell_alive: bool | None
    execution_recoverable: bool
    cursor: int
    next_cursor: int
    cursor_start: int
    cursor_end: int
    text: str
    stdout_delta: str
    stderr_delta: str
    chars: int
    available_chars: int
    has_more: bool
    eof: bool
    complete: bool
    timed_out: bool
    raw_available: bool
    requested_output_mode: str
    output_mode: str
    compaction_applied: bool
    stdout_lines: int
    stderr_lines: int
    stdout_chars: int
    stderr_chars: int
    returned_stdout_chars: int
    important_sections: list[str]
    wait_timeout_ms: int


class StopResult(ProtocolOutcome):
    protocol: str
    handshake_confirmed: bool
    request_id: str
    response_id: str
    cancelled: bool
    execution_id: str | None = None
    state: str | None = None
    reason: str | None = None
    targeted: bool = False


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


def _exception_source(exc):
    message = str(exc or "").lower()
    name = type(exc).__name__.lower()
    cause = getattr(exc, "__cause__", None)
    cause_name = type(cause).__name__.lower() if cause is not None else ""
    if (
        "adapter indisponivel" in message
        or "timed out" in message
        or "timeout" in name
        or "timeout" in cause_name
        or "connectionrefused" in cause_name
        or "urlerror" in cause_name
        or "connection reset" in message
        or "connection refused" in message
    ):
        return "transport"
    return "mcp"


def _safe_exchange(operation, payload, *, timeout):
    try:
        return ProtocolHTTPClient(timeout=timeout).exchange(operation, payload)
    except Exception as exc:
        source = _exception_source(exc)
        error_type = "TransportError" if source == "transport" else "MCPProtocolError"
        now = int(time.time() * 1000)
        execution_id = str((payload or {}).get("execution_id") or "")
        return {
            "request_syn": {
                "request_id": f"req_local_error_{now}",
                "operation": operation,
            },
            "response_syn": {
                "response_id": f"res_local_error_{now}",
            },
            "payload": {
                "operation_ok": False,
                "state": "ERROR",
                "execution_id": execution_id,
                "error_source": source,
                "error_type": error_type,
                "error_message": str(exc),
                "execution_recoverable": bool(execution_id),
            },
        }


def _wait_error_result(
    exchange,
    payload,
    *,
    execution_id,
    cursor,
    wait_timeout_ms,
    output_mode,
    raw_available,
):
    error_type = payload.get("error_type")
    return WaitResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        state="ERROR",
        runtime_state="ERROR",
        execution_id=execution_id,
        target=str(payload.get("target") or ""),
        exit_code=None,
        duration_ms=None,
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        **_stream_contract(""),
        error_source=payload.get("error_source") or _error_source(error_type) or "mcp",
        error_type=error_type,
        error_message=payload.get("error_message"),
        failed_command=payload.get("failed_command"),
        shell_alive=payload.get("shell_alive"),
        execution_recoverable=bool(
            payload.get("execution_recoverable", bool(execution_id))
        ),
        cursor=cursor,
        next_cursor=cursor,
        cursor_start=cursor,
        cursor_end=cursor,
        text="",
        stdout_delta="",
        stderr_delta="",
        chars=0,
        available_chars=0,
        has_more=False,
        eof=False,
        complete=False,
        timed_out=False,
        raw_available=bool(raw_available),
        requested_output_mode=output_mode,
        output_mode=output_mode,
        compaction_applied=False,
        stdout_lines=0,
        stderr_lines=0,
        stdout_chars=0,
        stderr_chars=0,
        returned_stdout_chars=0,
        important_sections=[],
        wait_timeout_ms=wait_timeout_ms,
    )


def _error_source(error_type):
    if not error_type:
        return None
    name = str(error_type).strip().lower()
    if (
        "transport" in name
        or "unavailable" in name
        or "urlerror" in name
        or "timeout" in name
        or "connection" in name
    ):
        return "transport"
    if "commanderror" in name or "commandcancel" in name:
        return "command"
    if "sessioninterrupted" in name or "shell" in name or "terminal" in name:
        return "shell"
    if "protocol" in name or "handshake" in name or "mcp" in name:
        return "mcp"
    if "command" in name or "cancel" in name:
        return "command"
    return "executor"


AUTO_COMPACT_THRESHOLD_CHARS = 12000
COMPACT_HEAD_CHARS = 2800
COMPACT_TAIL_CHARS = 2800
COMPACT_IMPORTANT_MAX = 24
COMPACT_IMPORTANT_LINE_CHARS = 360
COMPACT_RESPONSE_MAX_CHARS = 9000
IMPORTANT_KEYWORDS = ("ERROR", "FAIL", "WARNING", "WARN", "TRACEBACK")


def _stream_contract(output):
    return {
        "stdout": str(output or ""),
        "stderr": "",
        "stream_mode": "COMBINED",
        "streams_separated": False,
    }


def _normalize_output_mode(output_mode):
    mode = str(output_mode or "NORMAL").strip().upper()
    if mode not in {"NORMAL", "COMPACT", "RAW"}:
        raise ValueError("output_mode deve ser NORMAL COMPACT ou RAW")
    return mode


def _line_count(text):
    text = str(text or "")
    if not text:
        return 0
    return len(text.splitlines()) or 1


def _important_sections(text):
    sections = []
    seen = set()
    for line_number, line in enumerate(str(text or "").splitlines(), start=1):
        upper = line.upper()
        if not any(keyword in upper for keyword in IMPORTANT_KEYWORDS):
            continue
        clean = line
        if len(clean) > COMPACT_IMPORTANT_LINE_CHARS:
            clean = clean[: COMPACT_IMPORTANT_LINE_CHARS - 3] + "..."
        if clean in seen:
            continue
        seen.add(clean)
        sections.append(f"L{line_number}: {clean}")
        if len(sections) >= COMPACT_IMPORTANT_MAX:
            break
    return sections


def _compact_stdout(raw_output, execution_id):
    raw = str(raw_output or "")
    important = _important_sections(raw)
    head = raw[:COMPACT_HEAD_CHARS]
    tail = raw[-COMPACT_TAIL_CHARS:] if len(raw) > COMPACT_TAIL_CHARS else raw
    parts = [
        "[CODEBRIDGE COMPACT]",
        f"execution_id={execution_id}",
        f"raw_chars={len(raw)}",
        f"raw_lines={_line_count(raw)}",
        "raw_available=true",
        "",
        "[HEAD]",
        head,
    ]
    if important:
        parts.extend(["", "[IMPORTANT]", *important])
    parts.extend(["", "[TAIL]", tail, "", "[RAW available by execution_id]"])
    compact = "\n".join(parts)
    if len(compact) > COMPACT_RESPONSE_MAX_CHARS:
        compact = compact[: COMPACT_RESPONSE_MAX_CHARS - 28] + "\n[COMPACT response clipped]"
    return compact, important


def _result_mode_contract(raw_output, requested_mode, execution_id):
    requested = _normalize_output_mode(requested_mode)
    raw = str(raw_output or "")
    actual = requested
    if requested == "NORMAL" and len(raw) > AUTO_COMPACT_THRESHOLD_CHARS:
        actual = "COMPACT"

    important = _important_sections(raw)
    returned = raw
    applied = False
    if not raw:
        return {
            "requested_output_mode": requested,
            "output_mode": actual,
            "compaction_applied": False,
            "stdout": "",
            "stderr": "",
            "stdout_lines": 0,
            "stderr_lines": 0,
            "stdout_chars": 0,
            "stderr_chars": 0,
            "returned_stdout_chars": 0,
            "important_sections": [],
        }
    if actual == "COMPACT":
        if len(raw) > AUTO_COMPACT_THRESHOLD_CHARS or requested == "COMPACT":
            returned, important = _compact_stdout(raw, execution_id)
            applied = returned != raw

    return {
        "requested_output_mode": requested,
        "output_mode": actual,
        "compaction_applied": applied,
        "stdout": returned,
        "stderr": "",
        "stdout_lines": _line_count(raw),
        "stderr_lines": 0,
        "stdout_chars": len(raw),
        "stderr_chars": 0,
        "returned_stdout_chars": len(returned),
        "important_sections": important,
    }


def _exec_result(
    exchange,
    payload,
    *,
    target,
    output_mode,
    wait_timeout_ms,
    command=None,
):
    runtime_state = str(payload.get("state") or "ERROR")
    complete = runtime_state in {"FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"}
    state = "RUNNING" if runtime_state in {"CREATED", "RUNNING"} else runtime_state
    terminal_output = (payload.get("output") or "") if complete else ""
    error_type = payload.get("error_type")
    execution_id = str(payload.get("execution_id") or "")
    failed_command = payload.get("failed_command")
    if (
        not failed_command
        and command
        and runtime_state not in {"CREATED", "RUNNING", "FINISHED"}
    ):
        failed_command = command
    shell_alive = payload.get("shell_alive")
    execution_recoverable = bool(
        payload.get("execution_recoverable", bool(execution_id))
    )
    mode_contract = _result_mode_contract(
        terminal_output,
        output_mode,
        execution_id,
    ) if complete else _result_mode_contract("", output_mode, execution_id)
    return ExecResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        state=state,
        runtime_state=runtime_state,
        execution_id=execution_id,
        target=str(payload.get("target") or target or ""),
        exit_code=payload.get("exit_code") if complete else None,
        duration_ms=_duration_ms(
            payload.get("started_at"),
            payload.get("finished_at"),
        ),
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        output=mode_contract["stdout"],
        stdout=mode_contract["stdout"],
        stderr=mode_contract["stderr"],
        stream_mode="COMBINED",
        streams_separated=False,
        error_source=_error_source(error_type),
        error_type=error_type,
        error_message=payload.get("error_message"),
        failed_command=failed_command,
        shell_alive=shell_alive,
        execution_recoverable=execution_recoverable,
        raw_available=bool(payload.get("execution_id")),
        cursor=0,
        complete=complete,
        requested_output_mode=mode_contract["requested_output_mode"],
        output_mode=mode_contract["output_mode"],
        compaction_applied=mode_contract["compaction_applied"],
        stdout_lines=mode_contract["stdout_lines"],
        stderr_lines=mode_contract["stderr_lines"],
        stdout_chars=mode_contract["stdout_chars"],
        stderr_chars=mode_contract["stderr_chars"],
        returned_stdout_chars=mode_contract["returned_stdout_chars"],
        important_sections=mode_contract["important_sections"],
        wait_timeout_ms=wait_timeout_ms,
    )


@mcp.tool(
    name="codebridge_ping",
    description="[LEGACY] Diagnostico antigo. Prefira codebridge_status ou codebridge_capabilities.",
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
    name="codebridge_capabilities",
    description=(
        "Descobre capacidades, limites e politica de migracao da instalacao "
        "CodeBridge sem executar comandos."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        idempotent_hint=True,
        open_world_hint=False,
    ),
    structured_output=True,
)
def codebridge_capabilities() -> CapabilitiesResult:
    exchange = ProtocolHTTPClient().exchange("STATUS", {})
    payload = exchange["payload"]
    preferred_tools = [
        "codebridge_status",
        "codebridge_capabilities",
        "codebridge_exec",
        "codebridge_wait",
        "codebridge_stop",
        "codebridge_read_batch",
        "codebridge_prepare",
        "codebridge_execute_prepared",
        "codebridge_discard",
    ]
    legacy_tools = [
        {
            "name": "codebridge_ping",
            "replacement": "codebridge_status / codebridge_capabilities",
        },
        {
            "name": "codebridge_terminal",
            "replacement": "codebridge_exec or codebridge_prepare",
        },
        {
            "name": "codebridge_start",
            "replacement": "codebridge_exec(wait_timeout_ms=0)",
        },
        {
            "name": "codebridge_execution_status",
            "replacement": "codebridge_wait(wait_timeout_ms=0)",
        },
        {
            "name": "codebridge_v2_start",
            "replacement": "codebridge_exec",
        },
        {
            "name": "codebridge_v2_status",
            "replacement": "codebridge_wait(wait_timeout_ms=0)",
        },
        {
            "name": "codebridge_v2_result",
            "replacement": "codebridge_wait",
        },
        {
            "name": "codebridge_v2_output",
            "replacement": "codebridge_wait(wait_timeout_ms=0)",
        },
        {
            "name": "codebridge_v2_stop",
            "replacement": "codebridge_stop(execution_id=...)",
        },
    ]
    return CapabilitiesResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        app=payload.get("app"),
        version=payload.get("version"),
        targets=["POWERSHELL5.1", "CMD", "SSH"],
        features={
            "async_execution": True,
            "wait": True,
            "event_driven_wait": True,
            "stream_output": True,
            "prepare": True,
            "cancel": True,
            "targeted_cancel": True,
            "raw_output": True,
            "structured_errors": True,
            "compact_output": True,
            "output_delta": True,
            "hot_connection": True,
            "read_only_batch": True,
            "parallel_read_only": True,
        },
        limits={
            "exec_wait_timeout_max_ms": 10000,
            "wait_timeout_max_ms": 120000,
            "wait_max_chars": 262144,
            "compact_response_max_chars": 9000,
            "read_batch_max_items": 32,
            "read_batch_max_workers": 8,
        },
        preferred_tools=preferred_tools,
        legacy_tools=legacy_tools,
        migration={
            "stage": "STABILIZE",
            "legacy_tools_published": True,
            "legacy_removal_ready": False,
            "removal_gate": (
                "remove only after connected clients refresh their MCP schema "
                "and no longer depend on legacy tool names"
            ),
            "rollback": (
                "keep v2 operations available; never reexecute commands "
                "during fallback"
            ),
        },
    )


@mcp.tool(
    name="codebridge_read_batch",
    description=(
        "Executa em uma unica chamada um lote estritamente somente leitura. "
        "Kinds permitidos: GIT_STATUS GIT_HEAD GIT_BRANCH VERSION FILE_STAT SHA256. "
        "Nao aceita comandos arbitrarios nem operacoes mutaveis."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        idempotent_hint=True,
        open_world_hint=False,
    ),
    structured_output=True,
)
def codebridge_read_batch(
    operations: list[dict[str, Any]],
) -> ReadOnlyBatchResult:
    exchange = _safe_exchange(
        "READ_ONLY_BATCH",
        {"operations": operations},
        timeout=35.0,
    )
    payload = exchange["payload"]
    if not payload.get("operation_ok", True):
        raise ValueError(
            payload.get("error_message")
            or payload.get("error_type")
            or "read-only batch falhou"
        )
    return ReadOnlyBatchResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        count=int(payload.get("count", 0) or 0),
        ok_count=int(payload.get("ok_count", 0) or 0),
        error_count=int(payload.get("error_count", 0) or 0),
        complete=bool(payload.get("complete")),
        read_only=bool(payload.get("read_only")),
        parallel=bool(payload.get("parallel")),
        workers_used=int(
            payload.get("workers_used", 0) or 0
        ),
        max_workers=int(
            payload.get("max_workers", 0) or 0
        ),
        items=list(payload.get("items") or []),
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
    description="[LEGACY] Dispatch antigo. Prefira codebridge_exec para executar ou codebridge_prepare para preparar.",
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
    description="[LEGACY] Inicio assincrono antigo. Prefira codebridge_exec com wait_timeout_ms=0.",
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
    description="[LEGACY] Consulta antiga. Prefira codebridge_wait com wait_timeout_ms=0.",
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
    description="Executa pelo caminho v2 com modos NORMAL COMPACT RAW. NORMAL compacta automaticamente saidas grandes; RAW permanece recuperavel pelo execution_id.",
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
    output_mode = _normalize_output_mode(output_mode)

    start_exchange = _safe_exchange(
        "EXECUTION_V2_START",
        {"target": target, "command": command},
        timeout=12.0,
    )
    start_payload = start_exchange["payload"]
    if not start_payload.get("operation_ok", True):
        return _exec_result(
            start_exchange,
            start_payload,
            target=target,
            output_mode=output_mode,
            wait_timeout_ms=wait_timeout_ms,
            command=command,
        )

    execution_id = str(start_payload.get("execution_id") or "")
    if not execution_id:
        return _exec_result(
            start_exchange,
            start_payload,
            target=target,
            output_mode=output_mode,
            wait_timeout_ms=wait_timeout_ms,
            command=command,
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
        last_exchange = _safe_exchange(
            "EXECUTION_V2_STATUS",
            {"execution_id": execution_id},
            timeout=10.0,
        )
        last_payload = last_exchange["payload"]
        if not last_payload.get("operation_ok", True):
            return _exec_result(
                last_exchange,
                last_payload,
                target=target,
                output_mode=output_mode,
                wait_timeout_ms=wait_timeout_ms,
                command=command,
            )

    result_exchange = _safe_exchange(
        "EXECUTION_V2_RESULT",
        {"execution_id": execution_id},
        timeout=10.0,
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
        command=command,
    )


@mcp.tool(
    name="codebridge_wait",
    description="Aguarda por evento de nova saida ou estado terminal sem polling agressivo e retorna somente o delta desde o cursor. Timeout e RAW integral permanecem suportados.",
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
    output_mode: str = "NORMAL",
) -> WaitResult:
    execution_id = str(execution_id or "").strip()
    if not execution_id:
        raise ValueError("execution_id obrigatorio")

    cursor = max(0, int(cursor or 0))
    wait_timeout_ms = max(
        0,
        min(int(wait_timeout_ms or 0), 120000),
    )
    max_chars = max(
        1,
        min(int(max_chars or 32768), 262144),
    )
    output_mode = _normalize_output_mode(output_mode)

    output_exchange = _safe_exchange(
        "EXECUTION_V2_WAIT",
        {
            "execution_id": execution_id,
            "cursor": cursor,
            "max_chars": max_chars,
            "timeout_ms": wait_timeout_ms,
        },
        timeout=max(
            10.0,
            (wait_timeout_ms / 1000.0) + 10.0,
        ),
    )
    output_payload = output_exchange["payload"]

    if not output_payload.get("operation_ok", True):
        return _wait_error_result(
            output_exchange,
            output_payload,
            execution_id=execution_id,
            cursor=cursor,
            wait_timeout_ms=wait_timeout_ms,
            output_mode=output_mode,
            raw_available=bool(execution_id),
        )

    terminal_states = {
        "FINISHED",
        "FAILED",
        "CANCELLED",
        "INTERRUPTED",
    }
    runtime_state = str(
        output_payload.get("state") or "RUNNING"
    )
    state = (
        "RUNNING"
        if runtime_state in {"CREATED", "RUNNING"}
        else runtime_state
    )
    text = str(output_payload.get("text") or "")
    next_cursor = int(
        output_payload.get("next_cursor", cursor)
        or cursor
    )
    complete = bool(
        output_payload.get("complete")
    ) or runtime_state in terminal_states
    has_more = bool(output_payload.get("has_more"))
    eof = bool(output_payload.get("eof"))
    timed_out = bool(output_payload.get("timed_out"))

    structured_error_type = (
        output_payload.get("error_type")
        if complete
        else None
    )
    mode_contract = _result_mode_contract(
        text,
        output_mode,
        execution_id,
    )
    returned_delta = mode_contract["stdout"]

    return WaitResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=output_exchange[
            "request_syn"
        ]["request_id"],
        response_id=output_exchange[
            "response_syn"
        ]["response_id"],
        **_outcome_fields(output_payload),
        state=state,
        runtime_state=runtime_state,
        execution_id=execution_id,
        target=str(output_payload.get("target") or ""),
        exit_code=(
            output_payload.get("exit_code")
            if complete
            else None
        ),
        duration_ms=(
            _duration_ms(
                output_payload.get("started_at"),
                output_payload.get("finished_at"),
            )
            if complete
            else None
        ),
        started_at=output_payload.get("started_at"),
        finished_at=output_payload.get("finished_at"),
        stdout=returned_delta,
        stderr="",
        stream_mode="COMBINED",
        streams_separated=False,
        error_source=_error_source(
            structured_error_type
        ),
        error_type=structured_error_type,
        error_message=(
            output_payload.get("error_message")
            if complete
            else None
        ),
        failed_command=(
            output_payload.get("failed_command")
            if complete
            else None
        ),
        shell_alive=output_payload.get("shell_alive"),
        execution_recoverable=bool(
            output_payload.get(
                "execution_recoverable",
                bool(execution_id),
            )
        ),
        cursor=cursor,
        next_cursor=next_cursor,
        cursor_start=cursor,
        cursor_end=next_cursor,
        text=returned_delta,
        stdout_delta=returned_delta,
        stderr_delta="",
        chars=int(
            output_payload.get(
                "chars",
                len(text),
            )
            or 0
        ),
        available_chars=int(
            output_payload.get(
                "available_chars",
                len(text),
            )
            or 0
        ),
        has_more=has_more,
        eof=eof,
        complete=complete,
        timed_out=timed_out,
        raw_available=True,
        requested_output_mode=mode_contract[
            "requested_output_mode"
        ],
        output_mode=mode_contract["output_mode"],
        compaction_applied=mode_contract[
            "compaction_applied"
        ],
        stdout_lines=mode_contract["stdout_lines"],
        stderr_lines=mode_contract["stderr_lines"],
        stdout_chars=mode_contract["stdout_chars"],
        stderr_chars=mode_contract["stderr_chars"],
        returned_stdout_chars=mode_contract[
            "returned_stdout_chars"
        ],
        important_sections=mode_contract[
            "important_sections"
        ],
        wait_timeout_ms=wait_timeout_ms,
    )


@mcp.tool(
    name="codebridge_v2_start",
    description="[LEGACY] Rota v2 de inicio. Prefira codebridge_exec.",
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
    description="[LEGACY] Rota v2 de status. Prefira codebridge_wait com wait_timeout_ms=0.",
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
    description="[LEGACY] Rota v2 de resultado. Prefira codebridge_wait.",
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
    description="[LEGACY] Rota v2 de output. Prefira codebridge_wait com wait_timeout_ms=0.",
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
    description="[LEGACY] Rota v2 de cancelamento. Prefira codebridge_stop(execution_id=...).",
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
    description=(
        "Cancela de forma direcionada quando execution_id e informado. "
        "Sem execution_id preserva o comportamento compativel de interromper "
        "a execucao ativa ou descartar comando preparado."
    ),
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
    structured_output=True,
)
def codebridge_stop(
    execution_id: str | None = None,
) -> StopResult:
    execution_id = str(execution_id or "").strip() or None
    operation = (
        "EXECUTION_V2_STOP"
        if execution_id
        else "STOP"
    )
    request_payload = (
        {"execution_id": execution_id}
        if execution_id
        else {}
    )
    exchange = ProtocolHTTPClient(timeout=10.0).exchange(
        operation,
        request_payload,
    )
    payload = exchange["payload"]
    return StopResult(
        protocol="CBMCP/1",
        handshake_confirmed=True,
        request_id=exchange["request_syn"]["request_id"],
        response_id=exchange["response_syn"]["response_id"],
        **_outcome_fields(payload),
        cancelled=bool(payload.get("cancelled")),
        execution_id=(
            payload.get("execution_id")
            or execution_id
        ),
        state=payload.get("state"),
        reason=payload.get("reason"),
        targeted=bool(execution_id),
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
