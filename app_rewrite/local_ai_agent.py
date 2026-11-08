"""IA Local: conversa com ferramentas, aprovacao de comandos e Parar.

Roda cada mensagem numa thread e conversa com a interface por uma fila de
eventos (tipo, dado). Nenhum comando roda sem aprovacao explicita.
"""
from __future__ import annotations

import json
import queue
import re
import threading
import time
import uuid

from pathlib import Path

import local_ai_tools as tools
from local_ai_client import LocalAiCancelled

MAX_STEPS = 8
HISTORY_CHAR_BUDGET = 14000
COMMAND_OUTPUT_CHARS = 4000
COMMAND_TIMEOUT_SECONDS = 600

MENTIONED_FILE = re.compile(r"[\w./\\-]+\.[A-Za-z0-9]{1,8}")
MAX_MENTIONED_FILES = 2
LIST_INTENT = re.compile(r"\b(list\w*|pasta|diret\w*|quais\s+arquivos|conte\u00fado\s+d[ao])\b", re.I)
MENTIONED_DIR = re.compile(r"[\w./\\-]+")
CODE_EXTENSIONS = {".py", ".md", ".txt", ".json", ".js", ".ts", ".ps1", ".bat", ".cmd", ".sh",
                   ".yaml", ".yml", ".toml", ".ini", ".cfg", ".html", ".css", ".qss", ".nsi", ".sql"}
MENTIONED_FILE_LINES = 200

STATE_LABELS = {"FINISHED": "concluído", "FAILED": "falhou", "CANCELLED": "cancelado",
                "INTERRUPTED": "interrompido"}

MISSING_FILE_HINT = ("[Aviso do sistema] O arquivo %s NÃO existe na pasta do projeto (%s). "
                     "Não invente o conteúdo: diga ao usuário que não encontrou o arquivo e que ele "
                     "pode conferir o projeto selecionado na Central RAG.")

TERMINAL_NAMES = {"POWERSHELL5.1": "PowerShell", "CMD": "CMD", "SSH": "SSH"}

SYSTEM_PROMPT = """Você é a IA Local do CodeBridge: um assistente de programação experiente que roda no computador do usuário (Windows).
Responda em português do Brasil, de forma clara e objetiva. Use seu conhecimento geral de programação à vontade.
Pasta do projeto atual: {root}
Projeto na Central RAG: {project}

Você TEM acesso ao projeto por estas ferramentas:
- {rag_line}
- ler_arquivo: lê um arquivo do projeto (caminho relativo à pasta do projeto, até 300 linhas por vez).
- listar_pasta: mostra o conteúdo de uma pasta do projeto.
- executar_comando: roda um comando em POWERSHELL5.1, CMD ou SSH depois que o usuário aprovar.

As ferramentas são chamadas pelo sistema; o usuário não as vê.

Regras:
- Nunca escreva JSON de ferramenta nem nomes de ferramentas na resposta, e não explique como as ferramentas funcionam.
- Use executar_comando só quando o usuário pedir para rodar, ver ou verificar algo no computador. Para perguntas de "como fazer", responda com o código num bloco ```, sem executar.
- Quando o usuário pedir para ler, ver, listar ou rodar algo, use a ferramenta certa em vez de dizer que não consegue.
- Nunca invente nomes de arquivos, listas de pastas ou conteúdo que não esteja no contexto. Os trechos da Central RAG são só referência e podem estar desatualizados.
- Leia o arquivo antes de afirmar detalhes sobre o código e diga de qual arquivo veio a informação.
- Comandos: só o necessário e seguros; nunca apague, mova ou sobrescreva arquivos sem o usuário pedir. Se ele recusar um comando, não insista.
- Se realmente não souber algo, diga isso."""

TOOL_ARG_KEYS = {"name", "arguments", "terminal", "comando", "motivo", "caminho", "consulta",
                 "linha_inicial", "quantidade"}


def strip_tool_json(text: str) -> str:
    """Remove linhas que sao so o JSON de uma chamada de ferramenta (o 7B as vezes mostra)."""
    kept = []
    for line in str(text or "").splitlines():
        body = line.strip().strip("`")
        if body.startswith("{") and body.endswith("}"):
            try:
                data = json.loads(body)
            except ValueError:
                data = None
            if isinstance(data, dict) and data and set(data) <= TOOL_ARG_KEYS:
                continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def terminal_label(terminal: str) -> str:
    return TERMINAL_NAMES.get(terminal, terminal)


RAG_LINE_ON = "buscar_central_rag: busca trechos nos conhecimentos do projeto."
RAG_LINE_OFF = "(Central RAG desligada nesta conversa.)"


def message_chars(message: dict) -> int:
    size = len(str(message.get("content") or ""))
    for call in message.get("tool_calls") or []:
        size += len(json.dumps(call, ensure_ascii=False))
    return size


def trim_history(messages: list, budget: int = HISTORY_CHAR_BUDGET) -> list:
    """Remove as conversas mais antigas (inteiras) ate caber no orcamento."""
    messages = list(messages)
    while sum(message_chars(m) for m in messages) > budget:
        starts = [i for i, m in enumerate(messages) if m.get("role") == "user"]
        if len(starts) <= 1:
            break
        messages = messages[starts[1]:]
    return messages


class RuntimeCommandRunner:
    """Roda o comando pelo mesmo caminho v2 do MCP (aparece na aba do terminal)."""

    def __init__(self, runtime, poll_seconds: float = 0.5):
        self.runtime, self.poll_seconds = runtime, poll_seconds
        self.active_execution_id = None

    def run(self, terminal: str, command: str, cancelled) -> dict:
        request_id = "localai_" + uuid.uuid4().hex
        row = self.runtime.start_phase5b_local(request_id, terminal, command)
        execution_id = row["execution_id"]
        self.active_execution_id = execution_id
        stop_sent = False
        deadline = time.monotonic() + COMMAND_TIMEOUT_SECONDS
        try:
            while True:
                result = self.runtime.phase5c_execution_result(execution_id)
                if result.get("ready"):
                    return result
                if (cancelled() or time.monotonic() > deadline) and not stop_sent:
                    stop_sent = True
                    try:
                        self.runtime.stop_phase5d_execution(execution_id)
                    except Exception:
                        pass
                time.sleep(self.poll_seconds)
        finally:
            self.active_execution_id = None


class LocalAiAgent:
    def __init__(self, *, client_factory, ensure_ready, runner, search_fn,
                 project_id=lambda: "", project_root=lambda: None, on_activity=None):
        self.client_factory = client_factory
        self.ensure_ready = ensure_ready
        self.runner = runner
        self.search_fn = search_fn
        self.project_id = project_id
        self.project_root = project_root
        self.on_activity = on_activity or (lambda busy: None)
        self.events: queue.Queue = queue.Queue()
        self.history: list = []
        self.running = False
        self._cancel = threading.Event()
        self._decision = queue.Queue()
        self._thread = None

    # ---- comandos da interface -----------------------------------------
    def send(self, text: str, rag_enabled: bool = True) -> bool:
        text = str(text or "").strip()
        if not text or self.running:
            return False
        self.running = True
        self._cancel.clear()
        while not self._decision.empty():
            self._decision.get_nowait()
        self._thread = threading.Thread(target=self._turn, args=(text, rag_enabled),
                                        name="LocalAiTurn", daemon=True)
        self._thread.start()
        return True

    def cancel(self) -> None:
        self._cancel.set()
        self._decision.put(("cancel", None))

    def approve(self, command: str | None = None) -> None:
        self._decision.put(("approve", command))

    def reject(self) -> None:
        self._decision.put(("reject", None))

    def clear(self) -> bool:
        if self.running:
            return False
        self.history = []
        return True

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    # ---- uma mensagem do usuario ------------------------------------------
    def _emit(self, kind, data=None):
        self.events.put((kind, data))

    def _turn(self, text: str, rag_enabled: bool) -> None:
        self.on_activity(True)
        start_len = len(self.history)
        try:
            ok, error = self.ensure_ready(self.cancelled, lambda text: self._emit("status", text))
            if self.cancelled():
                raise LocalAiCancelled()
            if not ok:
                self._emit("error", error or "A IA não está ligada.")
                return
            parts = [self._file_context(text), self._dir_context(text),
                     self._rag_context(text) if rag_enabled else ""]
            context = "\n\n".join(part for part in parts if part)
            self.history.append({"role": "user", "content": text})
            self._loop(context, rag_enabled)
        except LocalAiCancelled:
            self._emit("note", "interrompido")
            del self.history[start_len:]
        except Exception as exc:  # erro mostrado na conversa, nunca derruba o app
            self._emit("error", str(exc) or type(exc).__name__)
            del self.history[start_len:]
        finally:
            self.history = trim_history(self.history)
            self.running = False
            self.on_activity(False)
            self._emit("turn_done")

    def _rag_context(self, text: str) -> str:
        self._emit("status", "Consultando a Central RAG…")
        try:
            result, note, paths = tools.rag_search(self.search_fn, self.project_id(), text)
        except Exception as exc:
            self._emit("note", "Central RAG indisponível: " + str(exc))
            return ""
        self._emit("note", note + (": " + ", ".join(paths[:4]) if paths else ""))
        return "" if not paths else "[Trechos da Central RAG — use se forem relevantes]\n" + result

    def _file_context(self, text: str) -> str:
        """Le na hora os arquivos do projeto citados na mensagem (o 7B costuma nao pedir)."""
        root, blocks, seen = self.project_root(), [], set()
        for match in MENTIONED_FILE.finditer(text):
            candidate = match.group(0).strip(".,;:!?)('\"`")
            if candidate in seen or len(blocks) >= MAX_MENTIONED_FILES:
                continue
            seen.add(candidate)
            looks_like_file = ("/" in candidate or "\\" in candidate
                               or Path(candidate).suffix.lower() in CODE_EXTENSIONS)
            if not root:
                if looks_like_file:
                    self._emit("note", "não li %s: nenhuma pasta de projeto na Central RAG" % candidate)
                    blocks.append(MISSING_FILE_HINT % (candidate, "(nenhuma)"))
                continue
            try:
                content, note = tools.read_file(root, candidate, 1, MENTIONED_FILE_LINES)
            except tools.ToolError as exc:
                if "protegido" in str(exc):
                    self._emit("note", "não li %s: arquivo protegido" % candidate)
                elif looks_like_file:
                    self._emit("note", "não encontrei %s na pasta %s" % (candidate, root))
                    blocks.append(MISSING_FILE_HINT % (candidate, root))
                continue
            except (OSError, ValueError):
                continue
            self._emit("note", note)
            blocks.append("[Conteúdo do arquivo citado]\n" + content)
        return tools.clip("\n\n".join(blocks), 7000) if blocks else ""

    def _dir_context(self, text: str) -> str:
        """Pedido para listar uma pasta do projeto: lista na hora (o 7B inventava a lista)."""
        root = self.project_root()
        if not root or not LIST_INTENT.search(text):
            return ""
        blocks, seen = [], set()
        for match in MENTIONED_DIR.finditer(text):
            candidate = match.group(0).strip(".,;:!?)('\"`/\\")
            if not candidate or candidate.lower() in seen or len(blocks) >= MAX_MENTIONED_FILES:
                continue
            seen.add(candidate.lower())
            try:
                path, _rel = tools.resolve_in_project(root, candidate)
                if not path.is_dir() or path == Path(root).resolve():
                    continue
                listing, note = tools.list_dir(root, candidate)
            except (tools.ToolError, OSError, ValueError):
                continue
            self._emit("note", note)
            blocks.append("[Conteúdo real da pasta citada \u2014 use exatamente esta lista]\n" + listing)
        return tools.clip("\n\n".join(blocks), 7000) if blocks else ""

    def _request_messages(self, context: str, rag_enabled: bool) -> list:
        system = SYSTEM_PROMPT.format(
            root=self.project_root() or "(nenhuma)", project=self.project_id() or "(nenhum)",
            rag_line=RAG_LINE_ON if rag_enabled else RAG_LINE_OFF,
        )
        messages = [{"role": "system", "content": system}] + [dict(m) for m in self.history]
        if context:
            for message in reversed(messages):
                if message["role"] == "user":
                    message["content"] = message["content"] + "\n\n" + context
                    break
        return messages

    def _loop(self, context: str, rag_enabled: bool) -> None:
        schemas = tools.tool_schemas(rag_enabled)
        for _ in range(MAX_STEPS):
            if self.cancelled():
                raise LocalAiCancelled()
            self._emit("status", "Pensando…")
            self._emit("assistant_start")
            reply = self.client_factory().chat(
                self._request_messages(context, rag_enabled), schemas,
                on_text=lambda piece: self._emit("text", piece), cancelled=self.cancelled,
            )
            reply["content"] = strip_tool_json(reply["content"])
            self._emit("assistant_done", reply["content"])
            calls = reply["tool_calls"]
            message = {"role": "assistant", "content": reply["content"]}
            if calls:
                message["tool_calls"] = calls
            self.history.append(message)
            if not calls:
                return
            for call in calls:
                result = self._run_tool(call)
                self.history.append({"role": "tool", "tool_call_id": call["id"],
                                     "content": tools.clip(result)})
        self._emit("note", "parei após %d passos; peça para continuar se quiser" % MAX_STEPS)

    # ---- ferramentas -----------------------------------------------------
    def _run_tool(self, call: dict) -> str:
        name = call["function"]["name"]
        try:
            arguments = tools.parse_arguments(call["function"].get("arguments"))
            if name == tools.TOOL_RAG:
                result, note, paths = tools.rag_search(self.search_fn, self.project_id(),
                                                       arguments.get("consulta", ""))
                self._emit("note", note + (": " + ", ".join(paths[:4]) if paths else ""))
                return result
            if name == tools.TOOL_READ:
                result, note = tools.read_file(self.project_root(), arguments.get("caminho", ""),
                                               arguments.get("linha_inicial", 1),
                                               arguments.get("quantidade", tools.DEFAULT_READ_LINES))
                self._emit("note", note)
                return result
            if name == tools.TOOL_LIST:
                result, note = tools.list_dir(self.project_root(), arguments.get("caminho", "."))
                self._emit("note", note)
                return result
            if name == tools.TOOL_RUN:
                return self._run_command(tools.validate_command(arguments))
            raise tools.ToolError("ferramenta desconhecida: " + str(name))
        except tools.ToolError as exc:
            self._emit("note", "ferramenta recusada: " + str(exc))
            return "ERRO: " + str(exc)

    def _run_command(self, request: dict) -> str:
        self._emit("status", "Aguardando sua aprovação")
        self._emit("approval", request)
        kind, edited = self._decision.get()
        self._emit("approval_closed")
        if kind == "cancel" or self.cancelled():
            raise LocalAiCancelled()
        if kind == "reject":
            self._emit("note", "você recusou o comando")
            return "O usuário recusou este comando. Não rode de novo; pergunte o que ele prefere."
        command = (edited or request["command"]).strip()
        terminal = request["terminal"]
        name = terminal_label(terminal)
        self._emit("status", "Executando no %s…" % name)
        self._emit("note", "executando no %s: %s" % (name, command.splitlines()[0][:120]))
        try:
            result = self.runner.run(terminal, command, self.cancelled)
        except Exception as exc:
            self._emit("note", "não consegui executar: " + str(exc))
            return "ERRO ao executar: " + str(exc)
        if self.cancelled():
            raise LocalAiCancelled()
        state, code = result.get("state"), result.get("exit_code")
        self._emit("note", "comando terminou (%s%s)" % (
            STATE_LABELS.get(str(state).upper(), str(state).lower()),
            "" if code is None else ", código %s" % code))
        output = tools.clip(result.get("output") or "(sem saída)", COMMAND_OUTPUT_CHARS)
        edited_note = "" if command == request["command"] else "O usuário editou o comando antes de rodar.\n"
        return "%sComando: %s\nEstado: %s  Código: %s\nSaída:\n%s" % (
            edited_note, command, state, code, output)

