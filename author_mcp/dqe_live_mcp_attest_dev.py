"""Read-only MCP HTTP probe for RAG-DEL DQ-E-F-1.

Uses the EXISTING local MCP process. No reload, tool mutation, model load
or installation. Run with author_mcp/.venv/Scripts/python.exe on Windows.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from rag.runtime.knowledge_deletion_live_mcp_attestation_dev import (
    review_live_generation_probe_dev,
)

LOCAL_ENDPOINT = "http://127.0.0.1:8765/mcp"
TOOL = "codebridge_rag_generation_probe"


async def inspect_live(*, expected_pid: int | None) -> dict:
    async with asyncio.timeout(12):
        async with streamable_http_client(LOCAL_ENDPOINT) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                listing = await session.list_tools()
                tool_names = [t.name for t in listing.tools]
                tool = next((t for t in listing.tools if t.name == TOOL), None)
                if tool is None:
                    return review_live_generation_probe_dev(
                        tool_names, {}, read_only_hint=False,
                        expected_pid=expected_pid,
                    )
                annotations = tool.annotations
                read_only = (
                    annotations is not None
                    and annotations.read_only_hint is True
                )
                if not read_only:
                    return review_live_generation_probe_dev(
                        tool_names, {}, read_only_hint=False,
                        expected_pid=expected_pid,
                    )
                response = await session.call_tool(TOOL, {})
                evidence = (
                    response.structured_content
                    if not response.is_error
                    and isinstance(response.structured_content, dict)
                    else {}
                )
                return review_live_generation_probe_dev(
                    tool_names, evidence, read_only_hint=read_only,
                    expected_pid=expected_pid,
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-pid", type=int, default=None)
    args = parser.parse_args()
    try:
        result = asyncio.run(inspect_live(expected_pid=args.expected_pid))
    except Exception as exc:
        # No traceback: network libraries can include sensitive URL details.
        result = {
            "state": "LIVE_MCP_ATTESTATION_BLOCKED",
            "error_type": type(exc).__name__,
            "live_mcp_probe_attested": False,
            "activation_authorized": False,
            "operational_use_allowed": False,
            "read_only": True,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["live_mcp_probe_attested"] else 1


if __name__ == "__main__":
    raise SystemExit(main())