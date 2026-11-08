"""IA Local: cliente do endpoint /v1/chat/completions do llama-server (streaming).

Junta os pedacos de texto e de chamadas de ferramenta (formato OpenAI). Como
reserva, tambem entende o formato de texto do Qwen: <tool_call>{...}</tool_call>.
"""
from __future__ import annotations

import http.client
import json
import re
import uuid

TOOL_CALL_TEXT = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


class LocalAiCancelled(Exception):
    pass


class LocalAiError(RuntimeError):
    pass


def parse_text_tool_calls(content: str):
    """Extrai <tool_call>{...}</tool_call> que o modelo escreveu como texto."""
    calls = []
    for match in TOOL_CALL_TEXT.finditer(content or ""):
        try:
            data = json.loads(match.group(1))
        except ValueError:
            continue
        name = data.get("name")
        if not isinstance(name, str):
            continue
        arguments = data.get("arguments", {})
        calls.append({
            "id": "call_" + uuid.uuid4().hex[:12],
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
        })
    cleaned = TOOL_CALL_TEXT.sub("", content or "").strip()
    return cleaned, calls


def merge_tool_call_deltas(calls: dict, deltas) -> None:
    for delta in deltas or []:
        index = delta.get("index", 0)
        slot = calls.setdefault(index, {"id": "", "type": "function",
                                        "function": {"name": "", "arguments": ""}})
        if delta.get("id"):
            slot["id"] = delta["id"]
        function = delta.get("function") or {}
        if function.get("name"):
            slot["function"]["name"] += function["name"]
        if function.get("arguments"):
            slot["function"]["arguments"] += function["arguments"]


class LocalAiClient:
    def __init__(self, port: int, api_key: str, *, timeout: float = 300.0):
        self.port, self.api_key, self.timeout = port, api_key, timeout

    def chat(self, messages, tools=None, *, on_text=None, cancelled=None,
             temperature: float = 0.2, max_tokens: int = 1500) -> dict:
        """Envia a conversa e devolve {"content": str, "tool_calls": list}."""
        body = {"messages": messages, "stream": True,
                "temperature": temperature, "max_tokens": max_tokens}
        if tools:
            body["tools"] = tools
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self.timeout)
        try:
            connection.request(
                "POST", "/v1/chat/completions",
                body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " + self.api_key},
            )
            response = connection.getresponse()
            if response.status != 200:
                detail = response.read(2000).decode("utf-8", "replace")
                raise LocalAiError("Servidor da IA respondeu %s: %s" % (response.status, detail))
            return self._read_stream(response, on_text, cancelled)
        except (OSError, http.client.HTTPException) as exc:
            if cancelled is not None and cancelled():
                raise LocalAiCancelled() from exc
            raise LocalAiError("Falha ao falar com a IA: " + str(exc)) from exc
        finally:
            connection.close()

    @staticmethod
    def _read_stream(response, on_text, cancelled) -> dict:
        text_parts, calls = [], {}
        for raw in response:
            if cancelled is not None and cancelled():
                raise LocalAiCancelled()
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                piece = delta.get("content")
                if piece:
                    text_parts.append(piece)
                    if on_text is not None:
                        on_text(piece)
                merge_tool_call_deltas(calls, delta.get("tool_calls"))
        content = "".join(text_parts)
        tool_calls = [calls[i] for i in sorted(calls) if calls[i]["function"]["name"]]
        for call in tool_calls:
            if not call["id"]:
                call["id"] = "call_" + uuid.uuid4().hex[:12]
        if not tool_calls and "<tool_call>" in content:
            content, tool_calls = parse_text_tool_calls(content)
        return {"content": content, "tool_calls": tool_calls}
