"""CodeBridge local launcher, independent of the editable project."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import tkinter as tk
from tkinter import messagebox

HOME = Path.home()
DEV = HOME / "CodeBridge-MCP-Bridge"
STABLE = HOME / "CodeBridge-Stable"
BASE = HOME / "CodeBridge-Launcher"
ENV = HOME / "CodeBridge-Runtime"
MANIFEST = BASE / "stable-manifest.json"
CANDIDATE_SELECTION = BASE / "selected-candidate.json"
LOGS = BASE / "logs"
APP_MUTEX = r"Local\CodeBridge.MCP.Bridge.v2"
LAUNCHER_MUTEX = r"Local\CodeBridge.Local.Launcher.v1"
KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
KERNEL.OpenMutexW.restype = wintypes.HANDLE
KERNEL.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
KERNEL.CreateMutexW.restype = wintypes.HANDLE
KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]


def app_running():
    handle = KERNEL.OpenMutexW(0x00100000, False, APP_MUTEX)
    if handle:
        KERNEL.CloseHandle(handle)
        return True
    error = ctypes.get_last_error()
    if error not in (0, 2):
        raise RuntimeError("Mutex do aplicativo inacessivel: %s" % error)
    return False


def check_tasks():
    query = (
        "Get-ScheduledTask | Where-Object {$_.TaskName -like 'CodeBridge*'} | "
        "ForEach-Object { $t = $_; $i = Get-ScheduledTaskInfo "
        "-TaskName $t.TaskName -ErrorAction SilentlyContinue; "
        "[pscustomobject]@{Name=$t.TaskName;State=[string]$t.State;"
        "NextRun=[string]$i.NextRunTime} } | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query],
        capture_output=True, text=True, timeout=20,
    )
    if result.returncode:
        raise RuntimeError("Nao foi possivel auditar tarefas agendadas")
    items = json.loads(result.stdout.strip() or "[]")
    if isinstance(items, dict):
        items = [items]
    for task in items:
        if task["State"] == "Running":
            raise RuntimeError("Tarefa ativa: " + task["Name"])
        if task["State"] != "Disabled" and task.get("NextRun", "").strip():
            raise RuntimeError("Tarefa com execucao futura: " + task["Name"])


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def selected_snapshot():
    if not CANDIDATE_SELECTION.exists():
        return STABLE, MANIFEST, ENV / "stable" / "Scripts" / "python.exe", None
    config = json.loads(CANDIDATE_SELECTION.read_text(encoding="utf-8"))
    commit = config.get("candidate_commit") if isinstance(config, dict) else None
    if (
        not isinstance(commit, str) or len(commit) != 40
        or any(c not in "0123456789abcdef" for c in commit)
    ):
        raise RuntimeError("Selecao de candidato invalida")
    name = "stable-candidate-" + commit[:7]
    root = HOME / ("CodeBridge-Stable-Candidate-" + commit[:7])
    manifest = BASE / ("stable-candidate-" + commit[:7] + ".json")
    python = ENV / name / "Scripts" / "python.exe"
    return root, manifest, python, commit


def check_snapshot(snapshot_root=None, manifest_file=None):
    snapshot_root = snapshot_root or STABLE
    manifest_file = manifest_file or MANIFEST
    if not manifest_file.is_file():
        raise RuntimeError("Manifesto do snapshot estavel ausente")
    info = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(info, dict):
        raise RuntimeError("Manifesto invalido")
    checksums = info.get("checksums")
    if info.get("state") != "CANDIDATE" or not isinstance(checksums, dict) or not checksums:
        raise RuntimeError("Manifesto invalido")
    if snapshot_root.is_symlink() or snapshot_root.is_junction():
        raise RuntimeError("Snapshot redirecionado")
    root = snapshot_root.resolve(strict=True)
    names = set()
    for relative, expected in checksums.items():
        rel = Path(relative)
        canonical = rel.as_posix().casefold()
        if (
            rel.is_absolute() or not rel.parts or ".." in rel.parts
            or ":" in relative or canonical in names
            or not isinstance(expected, str) or len(expected) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in expected)
        ):
            raise RuntimeError("Entrada insegura no manifesto")
        names.add(canonical)
        path = root / rel
        if not path.is_file() or path.is_symlink() or path.is_junction():
            raise RuntimeError("Arquivo ausente ou link: " + relative)
        if not path.resolve().is_relative_to(root) or digest(path) != expected:
            raise RuntimeError("Integridade falhou: " + relative)
    # Never start additional unverified Python/config sources from the stable snapshot.
    # Runtime-only files from the isolated MCP venv and Python bytecode are excluded.
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if ".venv" in rel.parts or "__pycache__" in rel.parts:
            continue
        if path.is_symlink() or path.is_junction():
            raise RuntimeError("Link inesperado no snapshot: " + str(rel))
        if path.is_file() and rel.as_posix().casefold() not in names:
            raise RuntimeError("Arquivo nao verificado no snapshot: " + str(rel))
    return info


def verify(mode, require_idle=True):
    if mode not in ("dev", "stable"):
        raise ValueError("Modo invalido")
    if mode == "dev":
        root = DEV
        python = ENV / "dev" / "Scripts" / "python.exe"
        manifest = None
        expected_commit = None
    else:
        root, manifest, python, expected_commit = selected_snapshot()
    main = root / "app_rewrite" / "main.py"
    mcp_python = root / "author_mcp" / ".venv" / "Scripts" / "python.exe"
    for item in (python, main, mcp_python):
        if not item.is_file():
            raise RuntimeError("Dependencia ausente: " + str(item))
    if mode == "stable":
        record_info = check_snapshot(root, manifest)
        if expected_commit is not None and record_info.get("source_commit") != expected_commit:
            raise RuntimeError("Commit do candidato nao confere")
    for interpreter, imports in (
        (python, "import PySide6,paramiko,psutil,qdrant_client"),
        (mcp_python, "import mcp,psutil"),
    ):
        proc = subprocess.run(
            [str(interpreter), "-c", imports],
            capture_output=True, timeout=30,
        )
        if proc.returncode:
            raise RuntimeError("Dependencias incompletas: " + str(interpreter))
    if require_idle:
        if app_running():
            raise RuntimeError("Ja existe um CodeBridge em execucao")
        with socket.socket() as sock:
            sock.settimeout(0.25)
            if sock.connect_ex(("127.0.0.1", 8765)) == 0:
                raise RuntimeError("Porta 8765 ocupada")
        check_tasks()
    return root, python


def record(message):
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "launcher.log").open("a", encoding="utf-8") as out:
        out.write(datetime.now().isoformat(timespec="seconds") + " " + message + "\n")


class Launcher:
    def __init__(self):
        self.lock = KERNEL.CreateMutexW(None, False, LAUNCHER_MUTEX)
        if not self.lock or ctypes.get_last_error() == 183:
            raise RuntimeError("Launcher ja esta aberto")
        self.root = tk.Tk()
        self.root.title("CodeBridge | Local")
        self.root.geometry("510x330")
        self.root.resizable(False, False)
        self.root.configure(bg="#10151d")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.process = None
        self.logfile = None
        tk.Label(self.root, text="CodeBridge", font=("Segoe UI", 24, "bold"),
                 fg="white", bg="#10151d").pack(pady=(24, 3))
        tk.Label(self.root, text="Execucao local sem reinstalar",
                 fg="#aab8c7", bg="#10151d").pack()
        self.status = tk.StringVar(value="Escolha um ambiente")
        tk.Label(self.root, textvariable=self.status, wraplength=470,
                 fg="#a5d3f0", bg="#10151d").pack(pady=(20, 15))
        for title, mode, color in [
            ("Iniciar desenvolvimento", "dev", "#217bbc"),
            ("Abrir snapshot local (candidato)", "stable", "#344f66"),
        ]:
            tk.Button(self.root, text=title, bg=color, fg="white", bd=0,
                      font=("Segoe UI", 11, "bold"), width=32, height=2,
                      command=lambda m=mode: self.start(m)).pack(pady=4)
        tk.Label(self.root, text="Sem Git push  |  sem reinstalacao  |  sem elevar privilegios",
                 fg="#9eacba", bg="#10151d").pack(pady=(15, 0))

    def start(self, mode):
        if self.process is not None:
            messagebox.showwarning("CodeBridge", "Feche o aplicativo atual primeiro")
            return
        try:
            root, python = verify(mode)
            LOGS.mkdir(parents=True, exist_ok=True)
            self.logfile = (LOGS / ("app_" + mode + ".log")).open(
                "a", encoding="utf-8", errors="replace"
            )
            self.process = subprocess.Popen(
                [str(python), str(root / "app_rewrite" / "main.py"), "--no-elevate"],
                cwd=str(root / "app_rewrite"), stdin=subprocess.DEVNULL,
                stdout=self.logfile, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            record("start mode=%s pid=%d" % (mode, self.process.pid))
            self.status.set("Modo %s iniciado | PID %d" % (mode, self.process.pid))
            self.root.after(1000, self.poll)
        except Exception as error:
            record("start_blocked mode=%s type=%s" % (mode, type(error).__name__))
            self.status.set("Inicializacao bloqueada")
            messagebox.showerror("CodeBridge", str(error))

    def poll(self):
        if self.process is None:
            return
        result = self.process.poll()
        if result is None:
            self.root.after(1000, self.poll)
            return
        record("exit pid=%d code=%d" % (self.process.pid, result))
        self.process = None
        self.logfile.close()
        self.logfile = None
        self.status.set("Aplicativo encerrado | codigo %d | pode trocar o modo" % result)

    def close(self):
        if self.process is not None and self.process.poll() is None:
            messagebox.showinfo("CodeBridge", "Feche o aplicativo antes de sair do launcher")
            return
        self.root.destroy()
        KERNEL.CloseHandle(self.lock)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", choices=["dev", "stable"])
    parser.add_argument("--idle", action="store_true")
    args = parser.parse_args()
    if args.check:
        root, python = verify(args.check, require_idle=args.idle)
        print("CHECK_OK", args.check, root, python)
    else:
        Launcher().run()
