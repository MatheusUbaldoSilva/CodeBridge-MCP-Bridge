"""Instalador das IAs do CodeBridge: llama-server, IA Local (Qwen) e modelos do RAG.

Roda no fim do CodeBridge-Setup.exe, pelo atalho "Configurar IAs" e pelo botao
"Verificar / Reparar IAs" da aba IA Local. Passos:
  1. olha o computador (placa NVIDIA e driver, memoria, disco);
  2. escolhe o llama-server (CUDA ou so CPU) e o tamanho do Qwen;
  3. baixa so o que falta, das fontes oficiais (GitHub do llama.cpp e
     Hugging Face), retomando downloads e conferindo tamanho e SHA-256, ou
     copia de um pacote offline;
  4. grava a configuracao (modelo da IA Local e chave CPU/GPU/Automatico);
  5. testa a IA Local (uma pergunta) e o RAG (texto e codigo).

Uso:
  ai_setup.py [--if-needed] [--installer] [--from PASTA] [--console] [--no-tests]
  ai_setup.py --check                so confere: 0 = pronto, 3 = falta algo
  ai_setup.py --make-package PASTA   baixa tudo para levar a outra maquina

Codigos de saida: 0 pronto, 1 erro, 2 cancelado, 3 falta algo (--check),
4 instalado mas um teste nao passou.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for _path in (str(HERE), str(ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from rag import llama_binary  # noqa: E402
from rag.models import backend_policy as text_policy  # noqa: E402
from rag.models import code_backend_policy as code_policy  # noqa: E402
from rag.models import compute_preference  # noqa: E402
from rag.models.artifact_install import resolve_selected_model_path  # noqa: E402
from rag.models.code_artifact_install import resolve_selected_code_model_path  # noqa: E402

import local_ai_server as srv  # noqa: E402

EXIT_OK, EXIT_ERROR, EXIT_CANCELLED, EXIT_MISSING, EXIT_TEST_FAILED = 0, 1, 2, 3, 4
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MB = 1048576
CHUNK = 1 << 20
USER_AGENT = "CodeBridge-ai-setup/1"

# ---- o que pode ser instalado ---------------------------------------------
LLAMA_BUILD = llama_binary.LLAMA_BUILD
MIN_CUDA_DRIVER = 528  # o llama.cpp CUDA 12.4 precisa do driver NVIDIA 528 ou mais novo
LLAMA_RELEASE = "https://github.com/ggml-org/llama.cpp/releases/download/b%d/" % LLAMA_BUILD


@dataclass(frozen=True)
class Artifact:
    key: str
    title: str
    name: str      # nome do arquivo (no download e no pacote offline)
    url: str
    size: int
    sha256: str
    license: str = ""


def _hf(repo: str, revision: str, filename: str) -> str:
    return "https://huggingface.co/%s/resolve/%s/%s?download=true" % (repo, revision, filename)


def _release(name: str) -> str:
    return LLAMA_RELEASE + name


LLAMA_CPU = Artifact(
    "llama_cpu", "llama-server (processador)", "llama-b10819-bin-win-cpu-x64.zip",
    _release("llama-b10819-bin-win-cpu-x64.zip"), 18413010,
    "4599e502b374196d24600ea9b03c842a448c853116a15b55e8ba502bdc727b3f", "MIT")
LLAMA_CUDA = Artifact(
    "llama_cuda", "llama-server (placa NVIDIA)", "llama-b10819-bin-win-cuda-12.4-x64.zip",
    _release("llama-b10819-bin-win-cuda-12.4-x64.zip"), 253945203,
    "8acca2d6464c968f9b17e664b093b23e21aada16a8f61b2191a3a588f56518a8", "MIT")
CUDART = Artifact(
    "cudart", "bibliotecas CUDA", "cudart-llama-bin-win-cuda-12.4-x64.zip",
    _release("cudart-llama-bin-win-cuda-12.4-x64.zip"), 391443627,
    "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6", "NVIDIA (redistribuível)")

QWEN = {
    "7B": Artifact(
        "qwen_7b", "IA Local — Qwen2.5-Coder 7B", "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        _hf("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", "13fb94bfda8c8cf22497dc57b78f391a9acb426a",
            "qwen2.5-coder-7b-instruct-q4_k_m.gguf"), 4683073536,
        "509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c", "Apache-2.0"),
    "3B": Artifact(
        "qwen_3b", "IA Local — Qwen2.5-Coder 3B", "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
        _hf("Qwen/Qwen2.5-Coder-3B-Instruct-GGUF", "f74adce6aa16316c625447af059dbebe4983757c",
            "qwen2.5-coder-3b-instruct-q4_k_m.gguf"), 2104932800,
        "724fb256bec1ff062b2f65e4569e871ad2e95ab2a3989723d1769c54294730b7", "Qwen Research"),
    "1.5B": Artifact(
        "qwen_1_5b", "IA Local — Qwen2.5-Coder 1.5B", "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        _hf("Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF", "f86cb2c1fa58255f8052cc32aeede1b7482d4361",
            "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"), 1117320768,
        "cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046", "Apache-2.0"),
}
RAG_TEXT = Artifact(
    "rag_text", "RAG texto — Jina v5", text_policy.TEXT_MODEL_FILENAME,
    _hf(text_policy.TEXT_RETRIEVAL_REPOSITORY, text_policy.TEXT_MODEL_REVISION,
        text_policy.TEXT_MODEL_FILENAME),
    text_policy.TEXT_MODEL_SIZE_BYTES, text_policy.TEXT_MODEL_SHA256, text_policy.TEXT_MODEL_LICENSE)
RAG_CODE = Artifact(
    "rag_code", "RAG código — Jina Code", code_policy.CODE_MODEL_FILENAME,
    _hf(code_policy.CODE_GGUF_REPOSITORY, code_policy.CODE_MODEL_REVISION,
        code_policy.CODE_MODEL_FILENAME),
    code_policy.CODE_MODEL_SIZE_BYTES, code_policy.CODE_MODEL_SHA256, code_policy.CODE_MODEL_LICENSE)

ALL_ARTIFACTS = (LLAMA_CPU, LLAMA_CUDA, CUDART, *QWEN.values(), RAG_TEXT, RAG_CODE)

STEPS = (
    ("hardware", "Verificar o computador"),
    ("llama", "llama-server"),
    ("local", "IA Local"),
    ("rag_text", "RAG texto — Jina v5"),
    ("rag_code", "RAG código — Jina Code"),
    ("config", "Gravar a configuração"),
    ("test_local", "Testar a IA Local"),
    ("test_rag", "Testar o RAG"),
)


# ---- caminhos ------------------------------------------------------------------
def data_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "CodeBridge"


def downloads_dir() -> Path:
    return data_root() / "downloads"


def state_file() -> Path:
    return srv.AI_DIR / "setup-state.json"


def report_file() -> Path:
    return srv.AI_DIR / "setup.json"


def qwen_target(size: str) -> Path:
    return srv.AI_DIR / "models" / QWEN[size].name


def model_targets(qwen_size: str) -> list:
    return [("local", QWEN[qwen_size], qwen_target(qwen_size)),
            ("rag_text", RAG_TEXT, resolve_selected_model_path()),
            ("rag_code", RAG_CODE, resolve_selected_code_model_path())]


def llama_artifacts(variant: str) -> tuple:
    return (LLAMA_CUDA, CUDART) if variant == "cuda" else (LLAMA_CPU,)


# ---- erros ------------------------------------------------------------------------
class SetupError(RuntimeError):
    """Falha com mensagem em portugues para a pessoa."""


class Cancelled(Exception):
    pass


# ---- computador ---------------------------------------------------------------------
@dataclass
class Hardware:
    gpu_name: str | None = None
    vram_mb: int | None = None
    driver: str | None = None
    ram_mb: int | None = None
    cpu_count: int = 0
    disk_free_mb: int | None = None

    @property
    def driver_major(self) -> int | None:
        try:
            return int(str(self.driver).split(".")[0])
        except (TypeError, ValueError):
            return None

    @property
    def cuda_ok(self) -> bool:
        return self.gpu_name is not None and (self.driver_major or 0) >= MIN_CUDA_DRIVER

    def describe(self) -> str:
        parts = []
        if self.gpu_name:
            parts.append("%s (%s, driver %s)" % (self.gpu_name, _gb(self.vram_mb * MB if self.vram_mb else 0),
                                                 self.driver or "?"))
        else:
            parts.append("sem placa NVIDIA")
        if self.ram_mb:
            parts.append("%s de RAM" % _gb(self.ram_mb * MB))
        if self.cpu_count:
            parts.append("%d núcleos" % self.cpu_count)
        if self.disk_free_mb is not None:
            parts.append("%s livres no disco" % _gb(self.disk_free_mb * MB))
        return " · ".join(parts)


def _existing(path: Path) -> Path:
    path = Path(path)
    while not path.exists() and path.parent != path:
        path = path.parent
    return path


def detect_hardware(run=subprocess.run, ram_bytes=None, disk_root=None) -> Hardware:
    hw = Hardware(cpu_count=os.cpu_count() or 0)
    try:
        out = run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                   "--format=csv,noheader,nounits"],
                  capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW)
        if out.returncode == 0 and (out.stdout or "").strip():
            name, total, driver = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")[:3]]
            hw.gpu_name, hw.vram_mb, hw.driver = name, int(float(total)), driver
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    if ram_bytes is None:
        try:
            import psutil
            ram_bytes = psutil.virtual_memory().total
        except Exception:
            ram_bytes = None
    hw.ram_mb = int(ram_bytes / MB) if ram_bytes else None
    try:
        hw.disk_free_mb = int(shutil.disk_usage(_existing(disk_root or data_root())).free / MB)
    except OSError:
        hw.disk_free_mb = None
    return hw


@dataclass
class Plan:
    variant: str   # "cuda" ou "cpu"
    qwen: str      # "7B", "3B" ou "1.5B"
    compute: str   # chave inicial do card IAs: "AUTO" ou "CPU"
    reason: str


def make_plan(hw: Hardware) -> Plan:
    notes = []
    if hw.cuda_ok:
        variant, compute = "cuda", "AUTO"
        notes.append("placa NVIDIA: llama-server com CUDA e modo Automático")
    else:
        variant, compute = "cpu", "CPU"
        if hw.gpu_name:
            notes.append("driver NVIDIA %s é antigo (precisa %d ou mais novo): tudo no processador"
                         % (hw.driver or "?", MIN_CUDA_DRIVER))
        else:
            notes.append("sem placa NVIDIA: tudo no processador")
    ram = hw.ram_mb or 0
    if variant == "cuda" and (hw.vram_mb or 0) >= 5800:
        qwen = "7B"
        notes.append("Qwen 7B na placa de vídeo")
    elif ram >= 15000:
        qwen = "7B"
        notes.append("Qwen 7B no processador (mais lento que na placa)")
    elif ram >= 7500:
        qwen = "3B"
        notes.append("Qwen 3B: memória para o 7B não sobra")
    else:
        qwen = "1.5B"
        notes.append("Qwen 1.5B: pouca memória")
    return Plan(variant, qwen, compute, "; ".join(notes))


# ---- arquivos -------------------------------------------------------------------------
def _gb(value_bytes) -> str:
    return ("%.1f GB" % ((value_bytes or 0) / (1024 ** 3))).replace(".", ",")


def sha256_file(path: Path, progress=None, cancelled=lambda: False) -> str:
    digest = hashlib.sha256()
    total = Path(path).stat().st_size
    done = 0
    with open(path, "rb") as handle:
        while True:
            if cancelled():
                raise Cancelled()
            block = handle.read(4 * CHUNK)
            if not block:
                break
            digest.update(block)
            done += len(block)
            if progress:
                progress(done, total)
    return digest.hexdigest()


class VerifiedCache:
    """Lembra arquivos ja conferidos (tamanho + data) para nao recalcular o SHA-256."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path or state_file())
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self.data = data if isinstance(data, dict) else {}

    def _record(self, path: Path):
        return self.data.get(str(Path(path)))

    def quick_valid(self, path: Path, art: Artifact) -> bool:
        path = Path(path)
        try:
            stat = path.stat()
        except OSError:
            return False
        record = self._record(path)
        return (stat.st_size == art.size and isinstance(record, dict)
                and record.get("sha256") == art.sha256 and record.get("size") == stat.st_size
                and record.get("mtime_ns") == stat.st_mtime_ns)

    def remember(self, path: Path, art: Artifact) -> None:
        stat = Path(path).stat()
        self.data[str(Path(path))] = {"sha256": art.sha256, "size": stat.st_size,
                                      "mtime_ns": stat.st_mtime_ns}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass

    def verify(self, path: Path, art: Artifact, progress=None, cancelled=lambda: False) -> bool:
        path = Path(path)
        if self.quick_valid(path, art):
            return True
        if not path.is_file() or path.stat().st_size != art.size:
            return False
        if sha256_file(path, progress, cancelled) != art.sha256:
            return False
        self.remember(path, art)
        return True


def download(art: Artifact, dest: Path, *, progress=None, cancelled=lambda: False,
             opener=None, retries: int = 8, sleep=time.sleep) -> Path:
    """Baixa art.url em dest, retomando de dest.part, e confere tamanho e SHA-256."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    opener = opener or urllib.request.build_opener().open
    last_error = None
    for attempt in range(retries):
        have = part.stat().st_size if part.exists() else 0
        if have > art.size:
            part.unlink()
            have = 0
        if have == art.size:
            break
        headers = {"User-Agent": USER_AGENT}
        if have:
            headers["Range"] = "bytes=%d-" % have
        try:
            with opener(urllib.request.Request(art.url, headers=headers), timeout=60) as response:
                status = getattr(response, "status", None) or response.getcode()
                if have and status != 206:  # servidor ignorou o Range: recomeca
                    have = 0
                with open(part, "ab" if have else "wb") as handle:
                    while True:
                        if cancelled():
                            raise Cancelled()
                        block = response.read(CHUNK)
                        if not block:
                            break
                        handle.write(block)
                        have += len(block)
                        if progress:
                            progress(have, art.size)
        except Cancelled:
            raise
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (403, 404, 410):
                break
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_error = exc
        if part.exists() and part.stat().st_size == art.size:
            break
        if attempt < retries - 1:
            sleep(min(2 ** attempt, 20))
    if not part.exists() or part.stat().st_size != art.size:
        raise SetupError("Não foi possível baixar %s (%s). Verifique a internet e tente de novo."
                         % (art.title, last_error or "download incompleto"))
    if sha256_file(part, None, cancelled) != art.sha256:
        part.unlink()
        raise SetupError("O arquivo baixado de %s veio corrompido (SHA-256 não confere). "
                         "Tente de novo." % art.title)
    os.replace(part, dest)
    return dest


def copy_verified(art: Artifact, source: Path, dest: Path, *, progress=None,
                  cancelled=lambda: False) -> Path:
    """Copia do pacote offline, conferindo o SHA-256 antes de publicar."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    done = 0
    with open(source, "rb") as src, open(part, "wb") as out:
        while True:
            if cancelled():
                raise Cancelled()
            block = src.read(4 * CHUNK)
            if not block:
                break
            out.write(block)
            done += len(block)
            if progress:
                progress(done, art.size)
    if part.stat().st_size != art.size or sha256_file(part, None, cancelled) != art.sha256:
        part.unlink()
        raise SetupError("O arquivo %s do pacote offline está corrompido." % art.name)
    os.replace(part, dest)
    return dest


# ---- llama-server -------------------------------------------------------------------
def llama_version(exe: Path, run=subprocess.run) -> int | None:
    try:
        out = run([str(exe), "--version"], capture_output=True, text=True, timeout=30,
                  creationflags=NO_WINDOW, cwd=str(Path(exe).parent))
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"build (\d+)", (out.stdout or "") + (out.stderr or ""))
    return int(match.group(1)) if match else None


def llama_ok(exe: Path, variant: str, run=subprocess.run) -> bool:
    exe = Path(exe)
    if not exe.is_file():
        return False
    if variant == "cuda" and not all((exe.parent / dll).is_file()
                                     for dll in ("ggml-cuda.dll", "cublas64_12.dll", "cudart64_12.dll")):
        return False
    return llama_version(exe, run) == LLAMA_BUILD


def _safe_members(archive: zipfile.ZipFile):
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts or ":" in name:
            raise SetupError("Arquivo inseguro dentro de %s: %s" % (archive.filename, info.filename))
        yield info


def extract_flat(zips, target: Path) -> Path:
    """Extrai os zips em target; se o llama-server vier dentro de uma pasta, sobe o conteudo."""
    target = Path(target)
    for path in zips:
        temp = target.with_name(target.name + ".tmp")
        shutil.rmtree(temp, ignore_errors=True)
        temp.mkdir(parents=True)
        with zipfile.ZipFile(path) as archive:
            archive.extractall(temp, members=list(_safe_members(archive)))
        root = temp
        entries = list(root.iterdir())
        while len(entries) == 1 and entries[0].is_dir():
            root = entries[0]
            entries = list(root.iterdir())
        for entry in entries:
            destination = target / entry.name
            if destination.is_dir():
                shutil.rmtree(destination)
            elif destination.exists():
                destination.unlink()
            shutil.move(str(entry), str(destination))
        shutil.rmtree(temp, ignore_errors=True)
    exe = target / "llama-server.exe"
    if not exe.is_file():
        raise SetupError("O pacote do llama-server não trouxe o llama-server.exe.")
    return exe


# ---- configuracao ------------------------------------------------------------------
def write_model_choice(model: Path, art: Artifact) -> None:
    path = srv.MODEL_CHOICE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"file": str(model), "name": srv.model_name_for(model),
                                "sha256": art.sha256}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def previous_qwen() -> str | None:
    """Tamanho do Qwen ja escolhido antes (respeita a escolha num reparo)."""
    chosen = srv.selected_model()
    for size, art in QWEN.items():
        if Path(chosen).name == art.name and srv.MODEL_CHOICE_FILE.is_file():
            return size
    return None


def configure_compute(plan: Plan, hw: Hardware) -> str:
    path = compute_preference.preference_file()
    if not path.is_file():
        return compute_preference.save_compute(plan.compute, path)
    current = compute_preference.load_compute(path)
    if current == "GPU" and not hw.cuda_ok:
        return compute_preference.save_compute("CPU", path)
    return current


# ---- testes ----------------------------------------------------------------------------
def ask_local_ai(port: int, api_key: str, timeout: float = 180) -> str:
    body = json.dumps({"messages": [{"role": "user", "content": "Responda apenas com a palavra OK."}],
                       "max_tokens": 8, "temperature": 0}).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:%d/v1/chat/completions" % port, data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    text = str(data["choices"][0]["message"].get("content") or "").strip()
    if not text:
        raise SetupError("A IA Local respondeu vazio.")
    return text[:40]


def test_local_ai(exe: Path, model: Path, cancelled=lambda: False, server_factory=None) -> str:
    server = (server_factory or srv.LocalAiServer)(exe=exe, model=model)
    if not server.start():
        raise SetupError(server.error or "A IA Local não ligou.")
    try:
        if not server.wait_ready(timeout=300, cancelled=cancelled):
            if cancelled():
                raise Cancelled()
            raise SetupError("A IA Local não ficou pronta: " + (server.error or "tempo esgotado"))
        answer = ask_local_ai(server.port, server.api_key)
        return "respondeu \"%s\" (%s)" % (answer, server.device or "?")
    finally:
        server.stop()


def test_rag(exe: Path) -> str:
    from rag.runtime import production_search
    text = production_search._embed_text("teste do instalador do CodeBridge", Path(exe))
    code = production_search._embed_code("funcao que soma dois numeros", Path(exe))
    if not len(text) or not len(code):
        raise SetupError("O RAG não gerou os vetores de teste.")
    return "texto %d e código %d dimensões" % (len(text), len(code))


# ---- execucao -------------------------------------------------------------------------
class Setup:
    """Executa os passos e avisa cada mudanca por emit(evento)."""

    def __init__(self, *, emit=lambda event: None, source_dir=None, run_tests: bool = True,
                 hardware=None, cache=None, opener=None, local_test=None, rag_test=None,
                 version_run=subprocess.run):
        self.emit = emit
        self.source_dir = Path(source_dir) if source_dir else None
        self.run_tests = run_tests
        self.hardware = hardware
        self.cache = cache
        self.opener = opener
        self.local_test = local_test or test_local_ai
        self.rag_test = rag_test or test_rag
        self.version_run = version_run
        self.cancel_event = threading.Event()
        self.plan = None
        self.result = None

    # -- eventos --
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def cancel(self) -> None:
        self.cancel_event.set()

    def step(self, key: str, state: str, detail: str = "") -> None:
        self.emit(("step", key, state, detail))

    def log(self, text: str) -> None:
        self.emit(("log", text))

    def _progress(self, label: str):
        last = [0.0]
        started = time.monotonic()

        def report(done, total):
            now = time.monotonic()
            if done < total and now - last[0] < 0.25:
                return
            last[0] = now
            speed = done / max(now - started, 0.001)
            self.emit(("progress", done, total, "%s · %s de %s · %.1f MB/s"
                       % (label, _gb(done), _gb(total), speed / MB)))
        return report

    # -- arquivos --
    def _offline(self, art: Artifact):
        if self.source_dir is None:
            return None
        candidate = self.source_dir / art.name
        return candidate if candidate.is_file() and candidate.stat().st_size == art.size else None

    def fetch(self, art: Artifact, dest: Path) -> None:
        source = self._offline(art)
        if source is not None:
            self.log("Copiando %s do pacote offline…" % art.name)
            copy_verified(art, source, dest, progress=self._progress("Copiando " + art.title),
                          cancelled=self.cancelled)
        else:
            self.log("Baixando %s (%s)…" % (art.name, _gb(art.size)))
            download(art, dest, progress=self._progress("Baixando " + art.title),
                     cancelled=self.cancelled, opener=self.opener)
        self.cache.remember(dest, art)

    def ensure_file(self, key: str, art: Artifact, dest: Path) -> Path:
        self.step(key, "run", "conferindo")
        if self.cache.verify(dest, art, self._progress("Conferindo " + art.title), self.cancelled):
            self.step(key, "ok", "já instalado · " + _gb(art.size))
            return dest
        self.step(key, "run", "baixando " + _gb(art.size))
        self.fetch(art, dest)
        self.step(key, "ok", "instalado · " + _gb(art.size))
        return dest

    def ensure_llama(self, variant: str) -> Path:
        self.step("llama", "run", "conferindo")
        current = llama_binary.llama_server_path()
        if llama_ok(current, variant, self.version_run):
            self.step("llama", "ok", "já instalado · %s" % current.parent)
            return current
        arts = llama_artifacts(variant)
        zips = []
        for art in arts:
            path = downloads_dir() / art.name
            if not self.cache.verify(path, art, None, self.cancelled):
                self.step("llama", "run", "baixando " + art.title)
                self.fetch(art, path)
            zips.append(path)
        self.step("llama", "run", "instalando")
        target = llama_binary.USER_LLAMA_DIR
        staging = target.with_name(target.name + ".new")
        old = target.with_name(target.name + ".old")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        exe = extract_flat(zips, staging)
        if llama_version(exe, self.version_run) != LLAMA_BUILD:
            raise SetupError("O llama-server instalado não abriu. Veja se o antivírus bloqueou %s." % staging)
        shutil.rmtree(old, ignore_errors=True)
        try:
            if target.exists():
                target.rename(old)
            staging.rename(target)
        except OSError as exc:
            raise SetupError("Não foi possível trocar o llama-server (%s). Feche o CodeBridge e as IAs "
                             "e tente de novo." % exc) from exc
        shutil.rmtree(old, ignore_errors=True)
        for path in zips:
            try:
                path.unlink()
            except OSError:
                pass
        installed = target / "llama-server.exe"
        self.step("llama", "ok", "instalado · %s" % target)
        return installed

    def _check_space(self, plan: Plan, hw: Hardware) -> None:
        needed = 0
        current = llama_binary.llama_server_path()
        if not llama_ok(current, plan.variant, self.version_run):
            needed += sum(a.size for a in llama_artifacts(plan.variant)) * 3  # zip + extraido + folga
        for _key, art, dest in model_targets(plan.qwen):
            if not (Path(dest).is_file() and Path(dest).stat().st_size == art.size):
                needed += art.size
        if needed and hw.disk_free_mb is not None and hw.disk_free_mb * MB < needed * 1.05:
            raise SetupError("Espaço insuficiente no disco: as IAs precisam de %s livres e há %s."
                             % (_gb(needed * 1.05), _gb(hw.disk_free_mb * MB)))

    # -- passos --
    def run(self) -> int:
        try:
            code = self._run()
        except Cancelled:
            self.emit(("done", EXIT_CANCELLED, "Cancelado. O que já foi baixado fica guardado para a próxima vez."))
            return EXIT_CANCELLED
        except SetupError as exc:
            self.emit(("done", EXIT_ERROR, str(exc)))
            return EXIT_ERROR
        except Exception as exc:  # pragma: no cover - erro inesperado
            self.emit(("done", EXIT_ERROR, "Erro inesperado: %s" % exc))
            return EXIT_ERROR
        return code

    def _run(self) -> int:
        self.cache = self.cache or VerifiedCache()
        self.step("hardware", "run")
        hw = self.hardware or detect_hardware()
        plan = make_plan(hw)
        kept = previous_qwen()
        if kept and kept != plan.qwen:
            plan.qwen = kept
            plan.reason += "; mantido o Qwen %s escolhido antes" % kept
        self.plan = plan
        self.step("hardware", "ok", hw.describe())
        self.emit(("plan", "Plano: " + plan.reason + "."))
        self._check_space(plan, hw)

        exe = self.ensure_llama(plan.variant)
        paths = {}
        for key, art, dest in model_targets(plan.qwen):
            paths[key] = self.ensure_file(key, art, dest)

        self.step("config", "run")
        write_model_choice(paths["local"], QWEN[plan.qwen])
        compute = configure_compute(plan, hw)
        report = {"hardware": asdict(hw), "plan": asdict(plan), "llama_server": str(exe),
                  "model": str(paths["local"]), "compute": compute,
                  "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.step("config", "ok", "IA Local: %s · processamento: %s"
                  % (srv.model_name_for(paths["local"]), {"AUTO": "Automático"}.get(compute, compute)))

        failures = []
        if self.run_tests:
            for key, label, test in (("test_local", "IA Local", lambda: self.local_test(exe, paths["local"], self.cancelled)),
                                     ("test_rag", "RAG", lambda: self.rag_test(exe))):
                self.step(key, "run", "carregando o modelo")
                try:
                    detail = test()
                    self.step(key, "ok", detail)
                except Cancelled:
                    raise
                except Exception as exc:
                    failures.append("%s: %s" % (label, exc))
                    self.step(key, "fail", str(exc))
        else:
            for key, _title in STEPS[-2:]:
                self.step(key, "skip", "testes pulados")
        report["tests"] = failures or "ok"
        try:
            report_file().write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass
        if failures:
            self.emit(("done", EXIT_TEST_FAILED, "IAs instaladas, mas um teste não passou: " + "; ".join(failures)
                       + ". Feche programas pesados e use Verificar / Reparar IAs."))
            return EXIT_TEST_FAILED
        self.emit(("done", EXIT_OK, "Pronto! IA Local e RAG instalados, configurados e testados. "
                   "Abra (ou reinicie) o CodeBridge para usar."))
        return EXIT_OK


def quick_check(hardware=None, cache=None, version_run=subprocess.run) -> list:
    """O que falta, sem baixar nem calcular SHA-256 (usa o que ja foi conferido)."""
    cache = cache or VerifiedCache()
    hw = hardware or detect_hardware()
    plan = make_plan(hw)
    plan.qwen = previous_qwen() or plan.qwen
    missing = []
    if not llama_ok(llama_binary.llama_server_path(), plan.variant, version_run):
        missing.append("llama-server")
    if not srv.MODEL_CHOICE_FILE.is_file():
        missing.append("configuração da IA Local")
    for _key, art, dest in model_targets(plan.qwen):
        if not cache.quick_valid(dest, art):
            missing.append(art.title)
    return missing


def make_package(folder: Path, emit=print, opener=None, cancelled=lambda: False) -> int:
    """Baixa todos os arquivos (as duas versoes do llama-server e os tres Qwen) numa pasta."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    cache = VerifiedCache(folder / "conferidos.json")
    for art in ALL_ARTIFACTS:
        dest = folder / art.name
        if cache.verify(dest, art):
            emit("ok   %s" % art.name)
            continue
        emit("baix %s (%s)" % (art.name, _gb(art.size)))
        download(art, dest, opener=opener, cancelled=cancelled)
        cache.remember(dest, art)
    (folder / "LEIA-ME.txt").write_text(
        "Pacote offline das IAs do CodeBridge.\r\n"
        "Coloque esta pasta, com o nome CodeBridge-IAs, ao lado do CodeBridge-Setup.exe\r\n"
        "ou rode: ai_setup.py --from \"%s\"\r\n" % folder, encoding="utf-8")
    emit("Pacote pronto em %s" % folder)
    return EXIT_OK


# ---- janela ------------------------------------------------------------------------
_DIALOG_CLASS = None
ICONS = {"wait": ("○", "#6e7d89"), "run": ("◔", "#d29922"), "ok": ("✔", "#3fb950"),
         "fail": ("✖", "#e5534b"), "skip": ("–", "#6e7d89")}


def dialog_class():
    global _DIALOG_CLASS
    if _DIALOG_CLASS is not None:
        return _DIALOG_CLASS
    from PySide6.QtCore import QObject, Qt, QTimer, Signal
    from PySide6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit,
                                   QProgressBar, QPushButton, QVBoxLayout)

    class Bridge(QObject):
        event = Signal(object)

    class SetupDialog(QDialog):
        def __init__(self, setup_factory, *, auto_start=True, parent=None):
            super().__init__(parent)
            self.setWindowTitle("CodeBridge · Configurar IAs")
            self.setMinimumWidth(640)
            self.setStyleSheet(
                "QDialog{background:#0d1117;color:#dfe7ee;}QLabel{color:#dfe7ee;}"
                "QPlainTextEdit{background:#0a1015;color:#9fb0bd;border:1px solid #33414d;}"
                "QPushButton{background:#1b242c;color:#dfe7ee;border:1px solid #33414d;"
                "border-radius:6px;padding:6px 16px;}QPushButton:hover{border-color:#4a5c6b;}"
                "QProgressBar{background:#0a1015;border:1px solid #33414d;border-radius:5px;"
                "color:#dfe7ee;text-align:center;height:16px;}"
                "QProgressBar::chunk{background:#2f9e44;border-radius:4px;}")
            self.setup_factory = setup_factory
            self.setup = None
            self.thread = None
            self.exit_code = None
            self.bridge = Bridge()
            self.bridge.event.connect(self.on_event)

            box = QVBoxLayout(self)
            title = QLabel("Configurar as IAs do CodeBridge")
            title.setStyleSheet("font-size:16px;font-weight:bold;")
            box.addWidget(title)
            self.plan_label = QLabel("Verificando o computador…")
            self.plan_label.setWordWrap(True)
            self.plan_label.setStyleSheet("color:#9fb0bd;")
            box.addWidget(self.plan_label)
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setColumnStretch(2, 1)
            self.icons, self.details = {}, {}
            for row, (key, text) in enumerate(STEPS):
                icon, name, detail = QLabel(), QLabel(text), QLabel()
                detail.setStyleSheet("color:#9fb0bd;")
                detail.setWordWrap(True)
                grid.addWidget(icon, row, 0)
                grid.addWidget(name, row, 1)
                grid.addWidget(detail, row, 2)
                self.icons[key], self.details[key] = icon, detail
                self.set_step(key, "wait", "")
            box.addLayout(grid)
            self.progress = QProgressBar()
            self.progress.setRange(0, 1000)
            self.progress.setValue(0)
            self.progress.setTextVisible(False)
            box.addWidget(self.progress)
            self.progress_label = QLabel("")
            self.progress_label.setStyleSheet("color:#9fb0bd;font-size:11px;")
            box.addWidget(self.progress_label)
            self.log = QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setMaximumHeight(110)
            box.addWidget(self.log)
            self.message = QLabel("")
            self.message.setWordWrap(True)
            box.addWidget(self.message)
            buttons = QHBoxLayout()
            buttons.addStretch(1)
            self.retry_button = QPushButton("Tentar de novo")
            self.retry_button.clicked.connect(self.start)
            self.retry_button.hide()
            self.action_button = QPushButton("Cancelar")
            self.action_button.clicked.connect(self.on_action)
            buttons.addWidget(self.retry_button)
            buttons.addWidget(self.action_button)
            box.addLayout(buttons)
            if auto_start:
                QTimer.singleShot(0, self.start)

        def set_step(self, key, state, detail):
            symbol, color = ICONS.get(state, ICONS["wait"])
            self.icons[key].setText(symbol)
            self.icons[key].setStyleSheet("color:%s;font-size:14px;font-weight:bold;" % color)
            if detail or state == "wait":
                self.details[key].setText(detail)

        def start(self):
            if self.thread is not None and self.thread.is_alive():
                return
            self.retry_button.hide()
            self.message.setText("")
            self.action_button.setText("Cancelar")
            self.exit_code = None
            for key, _text in STEPS:
                self.set_step(key, "wait", "")
            self.setup = self.setup_factory(self.bridge.event.emit)
            self.thread = threading.Thread(target=self.setup.run, name="AiSetup", daemon=True)
            self.thread.start()

        def on_event(self, event):
            kind = event[0]
            if kind == "step":
                _kind, key, state, detail = event
                self.set_step(key, state, detail)
                if state in ("ok", "fail", "skip"):
                    self.progress.setValue(0)
                    self.progress_label.setText("")
            elif kind == "progress":
                _kind, done, total, text = event
                self.progress.setValue(int(1000 * done / total) if total else 0)
                self.progress_label.setText(text)
            elif kind == "plan":
                self.plan_label.setText(event[1])
            elif kind == "log":
                self.log.appendPlainText(event[1])
            elif kind == "done":
                _kind, code, text = event
                self.exit_code = code
                color = "#3fb950" if code == EXIT_OK else ("#d29922" if code in (EXIT_TEST_FAILED, EXIT_CANCELLED)
                                                          else "#e5534b")
                self.message.setStyleSheet("color:%s;font-weight:bold;" % color)
                self.message.setText(text)
                self.log.appendPlainText(text)
                self.action_button.setText("Fechar")
                self.retry_button.setVisible(code != EXIT_OK)

        def on_action(self):
            if self.thread is not None and self.thread.is_alive():
                self.setup.cancel()
                self.action_button.setText("Cancelando…")
                return
            self.accept()

        def closeEvent(self, event):
            if self.thread is not None and self.thread.is_alive():
                self.setup.cancel()
                self.thread.join(timeout=15)
            super().closeEvent(event)

        def result_code(self) -> int:
            return EXIT_CANCELLED if self.exit_code is None else self.exit_code

    _DIALOG_CLASS = SetupDialog
    return SetupDialog


def launch_detached(extra=()) -> subprocess.Popen:
    """Abre este instalador numa janela propria (usado pelo botao da aba IA Local)."""
    python = Path(sys.executable)
    windowed = python.with_name("pythonw.exe")
    if windowed.is_file():
        python = windowed
    return subprocess.Popen([str(python), str(Path(__file__).resolve()), *extra], cwd=str(HERE))


def _console_emit(event) -> None:
    kind = event[0]
    if kind == "step":
        print("[%s] %s %s" % (event[2], dict(STEPS).get(event[1], event[1]), event[3]), flush=True)
    elif kind in ("plan", "log"):
        print(event[1], flush=True)
    elif kind == "done":
        print(event[2], flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Instala e configura as IAs do CodeBridge.")
    parser.add_argument("--check", action="store_true", help="só confere (0 pronto, 3 falta algo)")
    parser.add_argument("--if-needed", action="store_true", help="abre a janela só se faltar algo")
    parser.add_argument("--installer", action="store_true", help="chamado pelo CodeBridge-Setup.exe")
    parser.add_argument("--from", dest="source", help="pasta do pacote offline")
    parser.add_argument("--console", action="store_true", help="sem janela, texto no terminal")
    parser.add_argument("--no-tests", action="store_true", help="não testa as IAs no fim")
    parser.add_argument("--make-package", metavar="PASTA", help="baixa tudo para um pacote offline")
    args = parser.parse_args(argv)

    if args.make_package:
        try:
            return make_package(Path(args.make_package))
        except SetupError as exc:
            print(exc)
            return EXIT_ERROR
    if args.check or args.if_needed:
        missing = quick_check()
        if args.check:
            print("PRONTO" if not missing else "FALTA: " + ", ".join(missing))
            return EXIT_OK if not missing else EXIT_MISSING
        if not missing:
            return EXIT_OK

    def factory(emit):
        return Setup(emit=emit, source_dir=args.source, run_tests=not args.no_tests)

    if args.console:
        return factory(_console_emit).run()

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    dialog = dialog_class()(factory)
    dialog.exec()
    if dialog.thread is not None and dialog.thread.is_alive():
        dialog.setup.cancel()
        dialog.thread.join(timeout=15)
    del app
    return dialog.result_code()


if __name__ == "__main__":
    sys.exit(main())
