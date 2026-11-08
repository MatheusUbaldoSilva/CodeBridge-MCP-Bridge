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
from local_ai_format import strip_ansi

MAX_STEPS = 8
HISTORY_CHAR_BUDGET = 14000
COMMAND_OUTPUT_CHARS = 4000
DISPLAY_OUTPUT_CHARS = 20000  # o que aparece na conversa; o modelo recebe COMMAND_OUTPUT_CHARS
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

# Terminal que o usuario pediu pelo nome. O 7B ignorava "no terminal ssh" e usava PowerShell,
# entao o pedido explicito vira regra: so esse terminal fica no schema da decisao.
TERMINAL_WORDS = (
    ("SSH", re.compile(r"\bssh\b", re.I)),
    ("CMD", re.compile(r"\b(cmd|prompt de comando)\b", re.I)),
    ("POWERSHELL5.1", re.compile(r"\b(power\s?shell|pwsh)\b", re.I)),
)
TERMINAL_HINTS = {
    "SSH": ('O usuário pediu o terminal SSH (servidor Linux remoto, já conectado no CodeBridge): '
            'use "terminal": "SSH" e um comando Linux/bash, como ls -la, pwd, df -h ou cat arquivo. '
            'Não use comandos do PowerShell, caminhos do Windows nem Set-Location.'),
    "CMD": ('O usuário pediu o CMD: use "terminal": "CMD" e um comando do cmd.exe, '
            'como dir, type ou echo.'),
    "POWERSHELL5.1": 'O usuário pediu o PowerShell: use "terminal": "POWERSHELL5.1".',
}
RESULT_HEADER = "[Resultado da ação]"


def requested_terminal(text: str):
    """Terminal citado pelo nome no pedido (o primeiro que aparece), ou None."""
    found = []
    for terminal, pattern in TERMINAL_WORDS:
        match = pattern.search(str(text or ""))
        if match:
            found.append((match.start(), terminal))
    return min(found)[1] if found else None

SYSTEM_PROMPT = """Você é a IA Local do CodeBridge: um assistente de programação experiente que roda no computador do usuário (Windows).
Responda em português do Brasil, de forma clara e objetiva, falando diretamente com o usuário ("você"), nunca em terceira pessoa. Use seu conhecimento geral de programação à vontade.
Pasta do projeto atual: {root}
Projeto na Central RAG: {project}

O sistema executa ações por você (ler arquivos, listar pastas, buscar na Central RAG e rodar comandos que o usuário aprova) e coloca os resultados na conversa como [Resultado da ação]. Responda com base nesses resultados.

Regras:
- Nunca escreva JSON nem fale de ferramentas na resposta.
- Nunca invente nomes de arquivos, listas de pastas, saídas de comando ou conteúdo que não esteja na conversa. Os trechos da Central RAG são só referência e podem estar desatualizados.
- Diga de qual arquivo ou comando veio a informação.
- Para perguntas de "como fazer", responda com o código num bloco ```.
- Se o usuário recusou um comando, não insista; pergunte o que ele prefere.
- Se realmente não souber algo, diga isso.
- A saída completa dos comandos já aparece para o usuário logo acima da sua resposta. Não repita a saída: comente em poucas frases o que ela mostra (o que é importante, se deu erro)."""

DECISION_INSTRUCTION = """[Planejador interno — esta mensagem não é do usuário]
Escolha a PRÓXIMA ação para atender o último pedido do usuário. Responda só com o JSON.
- "responder": já dá para responder com o que está na conversa (resultados de ações, arquivos, trechos), ou é uma pergunta geral ou de "como fazer".
- "executar_comando": o usuário quer ver, verificar, testar ou rodar algo no computador (disco, memória, processos, rede, git, versões, testes). Use "terminal": "POWERSHELL5.1" e um comando do Windows PowerShell 5.1, salvo se ele pedir CMD ou SSH. Se o comando depender da pasta do projeto, comece com: Set-Location '{root}';
- "ler_arquivo": precisa ler um arquivo do projeto que ainda não está na conversa ("caminho" relativo à pasta do projeto).
- "listar_pasta": precisa ver uma pasta do projeto que ainda não está na conversa ("caminho" relativo).
{rag_option}Não repita uma ação cujo resultado já está na conversa depois do último pedido do usuário.
Exemplos:
"quanto espaço livre tem no disco C?" -> {{"acao": "executar_comando", "terminal": "POWERSHELL5.1", "comando": "Get-PSDrive -Name C | Select-Object Used,Free", "motivo": "ver o espaço livre do disco C"}}
"como faço um loop no PowerShell?" -> {{"acao": "responder", "motivo": "pergunta de como fazer"}}
"o que faz o arquivo app/main.py?" (ainda não lido) -> {{"acao": "ler_arquivo", "caminho": "app/main.py", "motivo": "ler o arquivo pedido"}}"""

RAG_OPTION = '- "buscar_central_rag": precisa procurar algo nos conhecimentos do projeto ("consulta").\n'
REJECTED_PREFIX = "O usuário recusou"
ANSWER = "responder"


def decision_schema(rag_enabled: bool, terminal: str | None = None) -> dict:
    actions = [ANSWER, tools.TOOL_RUN, tools.TOOL_READ, tools.TOOL_LIST]
    if rag_enabled:
        actions.append(tools.TOOL_RAG)
    terminals = [terminal] if terminal in tools.TERMINALS else list(tools.TERMINALS)
    return {"type": "object", "properties": {
        "acao": {"type": "string", "enum": actions},
        "terminal": {"type": "string", "enum": terminals},
        "comando": {"type": "string"},
        "caminho": {"type": "string"},
        "consulta": {"type": "string"},
        "motivo": {"type": "string"},
    }, "required": ["acao", "motivo"]}


def decision_to_call(decision, rag_enabled: bool, terminal: str | None = None):
    """JSON do planejador -> chamada de ferramenta, ou None para responder.

    Se o usuario pediu um terminal pelo nome, o comando vai para ele de qualquer jeito.
    """
    if not isinstance(decision, dict):
        return None
    action = decision.get("acao")
    if action == tools.TOOL_RUN:
        args = {"terminal": terminal or decision.get("terminal") or "POWERSHELL5.1",
                "comando": decision.get("comando") or "", "motivo": decision.get("motivo") or ""}
        if not args["comando"].strip():
            return None
    elif action in (tools.TOOL_READ, tools.TOOL_LIST):
        args = {"caminho": decision.get("caminho") or ("." if action == tools.TOOL_LIST else "")}
        if not args["caminho"].strip():
            return None
    elif action == tools.TOOL_RAG and rag_enabled:
        args = {"consulta": decision.get("consulta") or ""}
        if not args["consulta"].strip():
            return None
    else:
        return None
    return {"id": "call_" + uuid.uuid4().hex[:12], "type": "function",
            "function": {"name": action, "arguments": json.dumps(args, ensure_ascii=False)}}


def describe_call(call: dict) -> str:
    name = call["function"]["name"]
    try:
        args = json.loads(call["function"].get("arguments") or "{}")
    except ValueError:
        args = {}
    if name == tools.TOOL_RUN:
        return "rodei no %s: %s" % (terminal_label(str(args.get("terminal", ""))), args.get("comando", ""))
    if name == tools.TOOL_READ:
        return "li o arquivo %s" % args.get("caminho", "")
    if name == tools.TOOL_LIST:
        return "listei a pasta %s" % args.get("caminho", ".")
    if name == tools.TOOL_RAG:
        return "busquei na Central RAG: %s" % args.get("consulta", "")
    return name


def last_user_index(history: list) -> int:
    for index in range(len(history) - 1, -1, -1):
        if history[index].get("role") == "user":
            return index
    return -1


def plain_history(history: list, context: str = "") -> list:
    """Historico em texto simples (sem formato nativo de ferramentas): vale para qualquer modelo.

    Acoes de pedidos anteriores ficam de fora (so perguntas e respostas), para nao
    confundir o modelo; o contexto extra vai junto do ultimo pedido do usuario.
    """
    current = last_user_index(history)
    out = []
    for index, message in enumerate(history):
        role = message.get("role")
        is_action = role == "tool" or (role == "assistant" and message.get("tool_calls"))
        if is_action and index < current:
            continue
        if index == current and context:
            out.append({"role": "user", "content": str(message.get("content") or "") + "\n\n" + context})
            continue
        if role == "tool":
            out.append({"role": "user", "content": RESULT_HEADER + "\n" + str(message.get("content") or "")})
        elif role == "assistant" and message.get("tool_calls"):
            text = str(message.get("content") or "").strip()
            actions = "; ".join(describe_call(c) for c in message["tool_calls"])
            out.append({"role": "assistant", "content": (text + "\n" if text else "") + "(" + actions + ")"})
        else:
            out.append({"role": role, "content": str(message.get("content") or "")})
    return out


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
        if body == RESULT_HEADER:  # o 7B as vezes copia o cabecalho do resultado
            continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def terminal_label(terminal: str) -> str:
    return TERMINAL_NAMES.get(terminal, terminal)


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
        self._terminal = None

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
            self._terminal = requested_terminal(text)
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

    def _answer_messages(self, context: str) -> list:
        system = SYSTEM_PROMPT.format(root=self.project_root() or "(nenhuma)",
                                      project=self.project_id() or "(nenhum)")
        return [{"role": "system", "content": system}] + plain_history(self.history, context)

    def _decision_messages(self, context: str, rag_enabled: bool) -> list:
        instruction = DECISION_INSTRUCTION.format(root=self.project_root() or "(nenhuma)",
                                                  rag_option=RAG_OPTION if rag_enabled else "")
        if self._terminal:
            instruction += "\n" + TERMINAL_HINTS[self._terminal]
        return self._answer_messages(context) + [{"role": "user", "content": instruction}]

    def _decide(self, context: str, rag_enabled: bool):
        self._emit("status", "Decidindo o próximo passo\u2026")
        try:
            return self.client_factory().decide(self._decision_messages(context, rag_enabled),
                                                decision_schema(rag_enabled, self._terminal))
        except LocalAiCancelled:
            raise
        except Exception as exc:
            self._emit("note", "não consegui decidir a próxima ação (%s); respondendo direto" % exc)
            return None

    def _loop(self, context: str, rag_enabled: bool) -> None:
        """Decisao forcada: a cada passo o modelo escolhe uma acao num JSON obrigatorio."""
        done = set()
        for _ in range(MAX_STEPS):
            if self.cancelled():
                raise LocalAiCancelled()
            call = decision_to_call(self._decide(context, rag_enabled), rag_enabled, self._terminal)
            if self.cancelled():
                raise LocalAiCancelled()
            if call is None:
                break
            key = (call["function"]["name"], call["function"]["arguments"])
            if key in done:
                break
            done.add(key)
            self.history.append({"role": "assistant", "content": "", "tool_calls": [call]})
            result = self._run_tool(call)
            self.history.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": tools.clip(result)})
            # Um comando por pedido: depois de rodar (ou ser recusado) a IA so responde.
            # O 7B inventava tarefas extras (pediu "ls" e ele emendou um "df -h").
            if result.startswith(REJECTED_PREFIX) or call["function"]["name"] == tools.TOOL_RUN:
                break
        else:
            self._emit("note", "parei após %d ações; peça para continuar se quiser" % MAX_STEPS)
        self._answer(context)

    def _answer(self, context: str) -> None:
        if self.cancelled():
            raise LocalAiCancelled()
        self._emit("status", "Pensando\u2026")
        self._emit("assistant_start")
        reply = self.client_factory().chat(
            self._answer_messages(context), None,
            on_text=lambda piece: self._emit("text", piece), cancelled=self.cancelled,
        )
        content = strip_tool_json(reply["content"])
        if not content:
            content = "(a IA não escreveu uma resposta; tente perguntar de outro jeito)"
        self._emit("assistant_done", content)
        self.history.append({"role": "assistant", "content": content})

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
            return "O usuário recusou o comando; ele não foi executado."
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
        raw_output = result.get("output") or "(sem saída)"
        self._emit("output", tools.clip(raw_output, DISPLAY_OUTPUT_CHARS))  # saida real, sem passar pelo modelo
        output = tools.clip(strip_ansi(raw_output), COMMAND_OUTPUT_CHARS)  # modelo recebe sem codigos de cor
        edited_note = "" if command == request["command"] else "O usuário editou o comando antes de rodar.\n"
        return "%sComando: %s\nEstado: %s  Código: %s\nSaída:\n%s" % (
            edited_note, command, state, code, output)

