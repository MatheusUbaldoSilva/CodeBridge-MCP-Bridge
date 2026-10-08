import asyncio
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "author_mcp" / "mcp_server.py"

EXPECTED_RAG_TOOLS = {
    "codebridge_rag_status",
    "codebridge_rag_index",
    "codebridge_search_context",
    "codebridge_get_context",
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_port(port: int, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            raise RuntimeError(
                f"MCP server exited early rc={process.returncode}\n"
                f"stdout={stdout}\nstderr={stderr}"
            )
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise TimeoutError("MCP server did not open test port")


async def _exercise_rag_tools(port: int) -> dict[str, object]:
    url = f"http://127.0.0.1:{port}/mcp"
    async with streamable_http_client(url) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}

            missing = EXPECTED_RAG_TOOLS - names
            if missing:
                raise AssertionError(f"RAG MCP tools missing: {sorted(missing)}")

            status = await session.call_tool(
                "codebridge_rag_status",
                {},
            )
            index_plan = await session.call_tool(
                "codebridge_rag_index",
                {
                    "project_id": "codebridge",
                    "project_root": str(ROOT),
                    "scope": "BOTH",
                    "paths": [],
                    "execute": False,
                },
            )
            search = await session.call_tool(
                "codebridge_search_context",
                {
                    "query": "codebridge",
                    "project": "codebridge",
                    "top_k": 1,
                },
            )
            get_context = await session.call_tool(
                "codebridge_get_context",
                {
                    "project": "codebridge",
                    "chunk_ids": ["integration-missing-chunk"],
                    "include_document_content": False,
                    "allow_stale": False,
                },
            )

            return {
                "listed": sorted(EXPECTED_RAG_TOOLS),
                "status": status,
                "index_plan": index_plan,
                "search": search,
                "get_context": get_context,
            }


class RagRealMcpIntegrationTests(unittest.TestCase):
    def test_rag_tools_are_callable_over_real_streamable_http_mcp(self):
        port = _free_port()
        process = subprocess.Popen(
            [
                sys.executable,
                str(SERVER),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(ROOT / "author_mcp"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _wait_port(port, process)
            result = asyncio.run(_exercise_rag_tools(port))

            self.assertEqual(
                set(result["listed"]),
                EXPECTED_RAG_TOOLS,
            )

            for key in (
                "status",
                "index_plan",
                "search",
                "get_context",
            ):
                call_result = result[key]
                self.assertFalse(
                    call_result.is_error,
                    f"{key} returned MCP protocol/tool error: {call_result}",
                )
                self.assertIsNotNone(
                    call_result.structured_content,
                    f"{key} did not return structured output",
                )

            status_payload = result["status"].structured_content
            self.assertIn("operation_ok", status_payload)

            index_payload = result["index_plan"].structured_content
            self.assertTrue(index_payload["operation_ok"])
            self.assertEqual(index_payload["action"], "PLAN")
            self.assertFalse(index_payload["executed"])

            search_payload = result["search"].structured_content
            self.assertIn("operation_ok", search_payload)

            context_payload = result["get_context"].structured_content
            self.assertIn("operation_ok", context_payload)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
