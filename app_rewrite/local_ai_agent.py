"""IA Local: conversa com ferramentas, aprovacao de comandos e Parar.

Roda cada mensagem numa thread e conversa com a interface por uma fila de
eventos (tipo, dado). Nenhum comando roda sem aprovacao explicita.
"""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid

import local_ai_tools as tools
from local_ai_client import LocalAiCancelled

MAX_STEPS = 8
HISTORY_CHAR_BUDGET = 14000
COMMAND_OUTPUT_CHARS = 4000
COMMAND_TIMEOUT_SECONDS = 600

TERMINAL_NAMES = {"POWERSHELL5.1": "PowerShell", "CMD": "CMD", "SSH": "SSH"}

SYSTEM_PROMPT = """Você é a IA Local do CodeBridge, um assistente de programação que roda no computador do usuário (Windows).
Responda sempre em português do Brasil, de forma curta e direta.
Pasta do projeto atual: {root}
Projeto na Central RAG: {project}

Ferramentas:
- {rag_line}
- ler_arquivo: lê um arquivo do projeto (somente leitura, até 300 linhas por vez). Leia antes de afirmar algo sobre o código.
- listar_pasta: mostra o conteúdo de uma pasta do projeto.
- executar_comando: pede para rodar um comando em PowerShell 5.1, CMD ou SSH. O usuário aprova antes; se ele recusar, não insista no mesmo comando.

Regras:
- Use as ferramentas só quando precisar; para perguntas gerais, responda direto.
- Comandos devem ser seguros e somente o necessário. Nunca apague, mova ou sobrescreva arquivos sem o usuário pedir.
- Quando usar informação de um arquivo ou trecho, diga de qual arquivo veio.
- Se não souber, diga que não sabe."""

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
            context = self._rag_context(text) if rag_enabled else ""
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
        return "" if not paths else result

    def _request_messages(self, context: str, rag_enabled: bool) -> list:
        system = SYSTEM_PROMPT.format(
            root=self.project_root() or "(nenhuma)", project=self.project_id() or "(nenhum)",
            rag_line=RAG_LINE_ON if rag_enabled else RAG_LINE_OFF,
        )
        messages = [{"role": "system", "content": system}] + [dict(m) for m in self.history]
        if context:
            for message in reversed(messages):
                if message["role"] == "user":
                    message["content"] = (
                        message["content"] + "\n\n[Trechos da Central RAG — use se forem relevantes]\n"
                        + context)
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
            str(state).lower(), "" if code is None else ", código %s" % code))
        output = tools.clip(result.get("output") or "(sem saída)", COMMAND_OUTPUT_CHARS)
        edited_note = "" if command == request["command"] else "O usuário editou o comando antes de rodar.\n"
        return "%sComando: %s\nEstado: %s  Código: %s\nSaída:\n%s" % (
            edited_note, command, state, code, output)

