"""IA Local: ferramentas que o modelo pode pedir.

Leitura e busca rodam direto, sempre dentro da pasta do projeto e com limites.
Comandos nunca rodam sozinhos: viram um pedido de aprovacao para o usuario.
"""
from __future__ import annotations

import json
from pathlib import Path

MAX_READ_LINES = 300
DEFAULT_READ_LINES = 200
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_LIST_ENTRIES = 200
MAX_TOOL_RESULT_CHARS = 6000
RAG_TOP_K = 5
RAG_SNIPPET_CHARS = 700
TERMINALS = ("POWERSHELL5.1", "CMD", "SSH")

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache",
             ".pytest_cache", ".idea", ".vscode"}
BLOCKED_NAMES = {".env", "known_hosts", "authorized_keys", "id_rsa", "id_ed25519",
                 "id_ecdsa", "id_dsa", ".netrc", ".pypirc", ".git-credentials",
                 "credentials", "credentials.json", "secrets.json"}
BLOCKED_SUFFIXES = (".pem", ".key", ".pfx", ".p12", ".ppk", ".kdbx", ".env")
BLOCKED_PARTS = {".ssh", ".git", ".aws", ".gnupg"}

TOOL_RAG = "buscar_central_rag"
TOOL_READ = "ler_arquivo"
TOOL_LIST = "listar_pasta"
TOOL_RUN = "executar_comando"


class ToolError(ValueError):
    """Erro mostrado ao modelo como resultado da ferramenta."""


def tool_schemas(rag_enabled: bool) -> list[dict]:
    tools = [
        {"type": "function", "function": {
            "name": TOOL_READ,
            "description": "Le um arquivo de texto do projeto (somente leitura). "
                           "Devolve as linhas numeradas. Maximo de %d linhas por vez." % MAX_READ_LINES,
            "parameters": {"type": "object", "properties": {
                "caminho": {"type": "string", "description": "Caminho relativo a pasta do projeto."},
                "linha_inicial": {"type": "integer", "description": "Primeira linha (comeca em 1)."},
                "quantidade": {"type": "integer", "description": "Quantas linhas ler (ate %d)." % MAX_READ_LINES},
            }, "required": ["caminho"]},
        }},
        {"type": "function", "function": {
            "name": TOOL_LIST,
            "description": "Lista arquivos e pastas de uma pasta do projeto.",
            "parameters": {"type": "object", "properties": {
                "caminho": {"type": "string", "description": "Pasta relativa ao projeto. Use . para a raiz."},
            }},
        }},
        {"type": "function", "function": {
            "name": TOOL_RUN,
            "description": "Pede para rodar um comando num terminal do CodeBridge. O usuario precisa "
                           "aprovar antes. Use para listar, testar, consultar git etc. "
                           "POWERSHELL5.1 usa sintaxe do Windows PowerShell 5.1.",
            "parameters": {"type": "object", "properties": {
                "terminal": {"type": "string", "enum": list(TERMINALS)},
                "comando": {"type": "string"},
                "motivo": {"type": "string", "description": "Uma frase curta explicando o porque."},
            }, "required": ["terminal", "comando", "motivo"]},
        }},
    ]
    if rag_enabled:
        tools.insert(0, {"type": "function", "function": {
            "name": TOOL_RAG,
            "description": "Busca trechos relevantes nos conhecimentos da Central RAG do projeto.",
            "parameters": {"type": "object", "properties": {
                "consulta": {"type": "string", "description": "O que procurar."},
            }, "required": ["consulta"]},
        }})
    return tools


def parse_arguments(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw or "{}")
    except ValueError as exc:
        raise ToolError("argumentos invalidos (JSON): " + str(exc)) from exc
    if not isinstance(data, dict):
        raise ToolError("argumentos devem ser um objeto JSON")
    return data


def clip(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    head = limit * 2 // 3
    tail = limit - head
    return text[:head] + "\n[... %d caracteres omitidos ...]\n" % (len(text) - limit) + text[-tail:]


# ---- arquivos -------------------------------------------------------------
def is_blocked(relative: Path) -> bool:
    parts = [p.lower() for p in relative.parts]
    name = parts[-1] if parts else ""
    if any(p in BLOCKED_PARTS for p in parts[:-1]):
        return True
    return (name in BLOCKED_NAMES or name.startswith(".env")
            or name.endswith(BLOCKED_SUFFIXES))


def resolve_in_project(root, relative: str) -> tuple[Path, Path]:
    if not root:
        raise ToolError("nenhuma pasta de projeto configurada na Central RAG")
    base = Path(root).resolve()
    text = str(relative or ".").strip().strip('"').replace("\\", "/")
    candidate = Path(text)
    target = (candidate if candidate.is_absolute() else base / candidate).resolve()
    try:
        rel = target.relative_to(base)
    except ValueError:
        raise ToolError("fora da pasta do projeto: " + text) from None
    if rel.parts and is_blocked(rel):
        raise ToolError("arquivo protegido, leitura bloqueada: " + rel.as_posix())
    return target, rel


def read_file(root, caminho: str, linha_inicial=1, quantidade=DEFAULT_READ_LINES) -> tuple[str, str]:
    path, rel = resolve_in_project(root, caminho)
    if not path.is_file():
        raise ToolError("arquivo nao encontrado: " + rel.as_posix())
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ToolError("arquivo grande demais para ler (%d bytes)" % path.stat().st_size)
    raw = path.read_bytes()
    if b"\x00" in raw[:8192]:
        raise ToolError("arquivo binario, nao e texto: " + rel.as_posix())
    lines = raw.decode("utf-8", "replace").splitlines()
    start = max(1, int(linha_inicial or 1))
    count = max(1, min(int(quantidade or DEFAULT_READ_LINES), MAX_READ_LINES))
    end = min(len(lines), start + count - 1)
    if start > len(lines) and lines:
        raise ToolError("o arquivo tem so %d linhas" % len(lines))
    body = "\n".join("%5d  %s" % (i, lines[i - 1]) for i in range(start, end + 1))
    header = "%s (linhas %d-%d de %d)" % (rel.as_posix(), start, end, len(lines))
    note = "leu %s, linhas %d–%d" % (rel.as_posix(), start, end)
    return header + "\n" + body, note


def list_dir(root, caminho: str = ".") -> tuple[str, str]:
    path, rel = resolve_in_project(root, caminho)
    if not path.is_dir():
        raise ToolError("pasta nao encontrada: " + (rel.as_posix() or "."))
    entries = []
    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name in SKIP_DIRS:
            continue
        child_rel = rel / child.name
        if is_blocked(child_rel):
            continue
        entries.append(child.name + ("/" if child.is_dir() else ""))
        if len(entries) >= MAX_LIST_ENTRIES:
            entries.append("[... lista cortada em %d itens ...]" % MAX_LIST_ENTRIES)
            break
    shown = rel.as_posix() or "."
    return shown + ":\n" + "\n".join(entries or ["(vazia)"]), "listou a pasta " + shown


# ---- Central RAG -----------------------------------------------------------
def rag_search(search_fn, project_id: str, consulta: str, top_k: int = RAG_TOP_K) -> tuple[str, str, list]:
    if not str(consulta or "").strip():
        raise ToolError("consulta vazia")
    if not project_id:
        raise ToolError("nenhum projeto selecionado na Central RAG")
    data = search_fn(str(consulta), project_id, top_k) or {}
    hits = [h for h in (data.get("results") or []) if isinstance(h, dict)][:top_k]
    paths, blocks = [], []
    for number, hit in enumerate(hits, 1):
        meta = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
        path = str(hit.get("path") or hit.get("source_path") or meta.get("path")
                   or meta.get("source_path") or hit.get("document_path") or "?")
        text = str(hit.get("snippet") or hit.get("text") or hit.get("content") or "").strip()
        if path not in paths:
            paths.append(path)
        blocks.append("[%d] %s\n%s" % (number, path, clip(text, RAG_SNIPPET_CHARS)))
    if not blocks:
        return "Nada encontrado na Central RAG para: " + consulta, "consultou a Central RAG (0 trechos)", []
    note = "consultou a Central RAG (%d trecho%s)" % (len(blocks), "" if len(blocks) == 1 else "s")
    return "\n\n".join(blocks), note, paths


# ---- comando (precisa de aprovacao) ---------------------------------------
def validate_command(arguments: dict) -> dict:
    terminal = str(arguments.get("terminal") or "POWERSHELL5.1").strip().upper()
    aliases = {"POWERSHELL": "POWERSHELL5.1", "PS": "POWERSHELL5.1", "PWSH": "POWERSHELL5.1"}
    terminal = aliases.get(terminal, terminal)
    if terminal not in TERMINALS:
        raise ToolError("terminal invalido: %s (use %s)" % (terminal, ", ".join(TERMINALS)))
    command = str(arguments.get("comando") or "").strip()
    if not command or "\x00" in command:
        raise ToolError("comando vazio ou invalido")
    reason = str(arguments.get("motivo") or "").strip()
    return {"terminal": terminal, "command": command, "reason": reason}
