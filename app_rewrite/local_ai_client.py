"""IA Local: cliente do endpoint /v1/chat/completions do llama-server (streaming).

Junta os pedacos de texto e de chamadas de ferramenta (formato OpenAI). Como
reserva, tambem entende o formato de texto do Qwen: <tool_call>{...}</tool_call>.
"""
from __future__ import annotations

import http.client
import json
import re
import uuid

# Parametros recomendados pela Qwen para o Qwen2.5-Coder; com temperatura baixa o 7B entra em laco.
SAMPLING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "repeat_penalty": 1.05,
            "dry_multiplier": 0.8}
LOOP_WINDOW = 160
LOOP_REPEATS = 3
LOOP_NOTE = "\n\n[resposta cortada: a IA come\u00e7ou a se repetir]"


def repetition_cut(text: str, window: int = LOOP_WINDOW, repeats: int = LOOP_REPEATS):
    """Se o fim do texto ja apareceu varias vezes, devolve o texto ate a 2a copia; senao None."""
    if len(text) < window * repeats:
        return None
    tail = text[-window:]
    if text.count(tail) < repeats:
        return None
    first = text.find(tail)
    return text[:text.find(tail, first + 1)].rstrip()


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
    if not calls:
        raw_call = _raw_json_call(cleaned)
        if raw_call is not None:
            return "", [raw_call]
    return cleaned, calls


def _raw_json_call(text: str):
    """O Qwen2.5-Coder as vezes responde so com o JSON da chamada, sem <tool_call>."""
    body = (text or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", body, re.S)
    if fence:
        body = fence.group(1).strip()
    if not (body.startswith("{") and body.endswith("}")):
        return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    name, arguments = data.get("name"), data.get("arguments", {})
    if not isinstance(name, str) or not isinstance(arguments, (dict, str)):
        return None
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments, ensure_ascii=False)
    return {"id": "call_" + uuid.uuid4().hex[:12], "type": "function",
            "function": {"name": name, "arguments": arguments}}


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
             max_tokens: int = 1500, **sampling) -> dict:
        """Envia a conversa e devolve {"content": str, "tool_calls": list}."""
        body = {"messages": messages, "stream": True, "max_tokens": max_tokens}
        body.update(SAMPLING)
        body.update(sampling)
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
        text, calls, checked, looped = "", {}, 0, False
        for raw in response:
            if looped:
                break
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
                    text += piece
                    if on_text is not None:
                        on_text(piece)
                    if len(text) - checked >= 120:
                        checked = len(text)
                        cut = repetition_cut(text)
                        if cut is not None:
                            text, looped = cut + LOOP_NOTE, True
                            break
                merge_tool_call_deltas(calls, delta.get("tool_calls"))
        content = text
        tool_calls = [calls[i] for i in sorted(calls) if calls[i]["function"]["name"]]
        for call in tool_calls:
            if not call["id"]:
                call["id"] = "call_" + uuid.uuid4().hex[:12]
        if not tool_calls and ("<tool_call>" in content or content.strip().endswith(("}", "```"))):
            content, tool_calls = parse_text_tool_calls(content)
        return {"content": content, "tool_calls": tool_calls}
