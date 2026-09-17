import argparse
import hmac
import os
from datetime import datetime, timezone
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from http_client import ProtocolHTTPClient


class PingResult(BaseModel):
    status: str
    mensagem: str
    desafio: str
    executor_conectado: bool
    timestamp_utc: str


class ProtocolOutcome(BaseModel):
    operation_ok: bool = True
    operation_error_type: str | None = None
    operation_error_message: str | None = None


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


mcp = MCPServer(
    name="CodeBridge Autoral",
    description="MCP autoral do CodeBridge. Terminal visivel, execucao assincrona e retorno persistente.",
    version="0.7.0",
)


def _outcome_fields(payload):
    return {
        "operation_ok": bool(payload.get("operation_ok", True)),
        "operation_error_type": payload.get("error_type"),
        "operation_error_message": payload.get("error_message"),
    }


@mcp.tool(
    name="codebridge_ping",
    description="Diagnostico simples do MCP autoral sem acessar terminais.",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    structured_output=True,
)
def codebridge_ping(desafio: str) -> PingResult:
    return PingResult(
        status="ok",
        mensagem="CODEBRIDGE_AUTHOR_OK",
        desafio=desafio,
        executor_conectado=False,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
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


class BearerAuthMiddleware:
    def __init__(self, app, token: str):
        if not token:
            raise ValueError("Bearer token vazio")
        self.app = app
        self.expected = ("Bearer " + token).encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            supplied = headers.get(b"authorization", b"")
            if not hmac.compare_digest(supplied, self.expected):
                body = b'{"error":"unauthorized"}'
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                        (b"www-authenticate", b"Bearer"),
                    ],
                })
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def build_security(public_host: str | None, port: int) -> TransportSecuritySettings:
    allowed_hosts = [f"127.0.0.1:{port}", f"localhost:{port}"]
    allowed_origins = [f"http://127.0.0.1:{port}", f"http://localhost:{port}"]
    if public_host:
        host = public_host.strip().removeprefix("https://").removeprefix("http://").rstrip("/")
        allowed_hosts.append(host)
        allowed_origins.append("https://" + host)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def main():
    parser = argparse.ArgumentParser(description="CodeBridge MCP autoral")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--public-host", default=None)
    parser.add_argument("--require-bearer", action="store_true")
    args = parser.parse_args()
    security = build_security(args.public_host, args.port)
    if args.require_bearer:
        token = os.environ.get("CODEBRIDGE_MCP_BEARER_TOKEN", "").strip()
        if not token:
            raise RuntimeError("CODEBRIDGE_MCP_BEARER_TOKEN ausente")
        import uvicorn
        app = mcp.streamable_http_app(
            streamable_http_path="/mcp",
            transport_security=security,
            host=args.host,
        )
        app = BearerAuthMiddleware(app, token)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        return
    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path="/mcp",
        transport_security=security,
    )


if __name__ == "__main__":
    main()
