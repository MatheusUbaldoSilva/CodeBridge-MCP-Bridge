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
    error_type: str | None
    error_message: str | None
    raw_available: bool
    cursor: int
    complete: bool
    output_mode: str
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


def _exec_result(exchange, payload, *, target, output_mode, wait_timeout_ms):
    runtime_state = str(payload.get("state") or "ERROR")
    complete = runtime_state in {"FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"}
    state = "RUNNING" if runtime_state in {"CREATED", "RUNNING"} else runtime_state
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
        output=(payload.get("output") or "") if complete else "",
        error_type=payload.get("error_type") if complete else None,
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
