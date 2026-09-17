import ctypes
import difflib
import os
import queue
import struct
import threading
import time
from datetime import datetime
from pathlib import Path

from constants import DATA_DIR


class DevWatcher:
    EXTENSIONS = {
        ".py", ".ps1", ".psm1", ".cmd", ".bat",
        ".json", ".toml", ".yml", ".yaml", ".md", ".txt",
    }
    EXCLUDED_EXACT = {".git", ".venv", "__pycache__", "node_modules"}

    def __init__(self, root, max_file_bytes=1_000_000, debounce=0.18):
        self.root = Path(root).resolve()
        self.max_file_bytes = int(max_file_bytes)
        self.debounce = float(debounce)
        self.history_path = DATA_DIR / "development_history.log"
        self._snapshots = {}
        self._events = queue.Queue()
        self._stop = threading.Event()
        self._thread = None
        self._handle = None
        self._baseline_count = 0
        self._ready = threading.Event()

    @property
    def running(self):
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    @property
    def baseline_count(self):
        return self._baseline_count

    @property
    def ready(self):
        return self._ready.is_set()

    def _eligible(self, path):
        if path.suffix.lower() not in self.EXTENSIONS:
            return False
        for part in path.parts:
            lower = part.lower()
            if lower in self.EXCLUDED_EXACT:
                return False
            if lower.startswith("app_legacy_snapshot"):
                return False
        return True
    def _read_text(self, path):
        try:
            if not path.is_file() or path.stat().st_size > self.max_file_bytes:
                return None
            return path.read_text(encoding="utf-8-sig", errors="replace")
        except (OSError, UnicodeError):
            return None

    def _baseline(self):
        snapshots = {}
        try:
            iterator = self.root.rglob("*")
            for path in iterator:
                try:
                    if not path.is_file() or not self._eligible(path):
                        continue
                    text = self._read_text(path)
                    if text is not None:
                        snapshots[path] = text
                except OSError:
                    continue
        except OSError:
            pass
        self._snapshots = snapshots
        self._baseline_count = len(snapshots)
        self._ready.set()

    def start(self):
        if self.running:
            return False
        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="CodeBridgeDevWatcher", daemon=True)
        self._thread.start()
        return True
    def stop(self, timeout=2.0):
        self._stop.set()
        if os.name == "nt" and self._handle:
            try:
                ctypes.windll.kernel32.CancelIoEx(self._handle, None)
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        self._thread = None
        self._handle = None
        return True

    def drain_events(self, max_events=100):
        result = []
        for _ in range(max(1, int(max_events))):
            try:
                result.append(self._events.get_nowait())
            except queue.Empty:
                break
        return result

    def history_tail(self, max_bytes=250_000):
        path = self.history_path
        if not path.is_file():
            return ""
        try:
            with path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - int(max_bytes)))
                data = handle.read()
            return data.decode("utf-8", errors="replace")
        except OSError:
            return ""
    def _emit(self, event_text):
        text = str(event_text).rstrip() + "\n\n"
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with self.history_path.open("a", encoding="utf-8") as handle:
                handle.write(text)
        except OSError:
            pass
        self._events.put(text)

    def _diff_path(self, path):
        old = self._snapshots.get(path)
        new = self._read_text(path) if self._eligible(path) else None
        if old == new:
            return
        if new is None:
            self._snapshots.pop(path, None)
        else:
            self._snapshots[path] = new
        relative = str(path.relative_to(self.root))
        stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        lines = list(difflib.unified_diff(
            (old or "").splitlines(),
            (new or "").splitlines(),
            fromfile=relative + " (antes)",
            tofile=relative + " (agora)",
            lineterm="",
            n=2,
        ))
        if len(lines) > 300:
            lines = lines[:300] + ["... diff truncado ..."]
        self._emit(f"[{stamp}] ALTERACAO: {relative}\n" + "\n".join(lines))
    def _run(self):
        self._baseline()
        if self._stop.is_set():
            return
        if os.name == "nt":
            try:
                self._run_windows()
                return
            except Exception as exc:
                self._emit(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] WATCHER WINDOWS FALHOU: {type(exc).__name__}: {exc}")
        self._run_polling_fallback()

    def _run_polling_fallback(self):
        while not self._stop.wait(1.0):
            current_paths = set()
            try:
                iterator = self.root.rglob("*")
                for path in iterator:
                    if path.is_file() and self._eligible(path):
                        current_paths.add(path)
            except OSError:
                continue
            changed = current_paths | set(self._snapshots)
            for path in changed:
                if self._stop.is_set():
                    return
                self._diff_path(path)
    def _run_windows(self):
        kernel32 = ctypes.windll.kernel32
        FILE_LIST_DIRECTORY = 0x0001
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        FILE_SHARE_DELETE = 0x00000004
        OPEN_EXISTING = 3
        FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
        notify_filter = 0x00000001 | 0x00000002 | 0x00000008 | 0x00000010
        handle = kernel32.CreateFileW(
            str(self.root), FILE_LIST_DIRECTORY,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None,
        )
        invalid = ctypes.c_void_p(-1).value
        if handle == invalid:
            raise ctypes.WinError()
        self._handle = handle
        buffer = ctypes.create_string_buffer(64 * 1024)
        bytes_returned = ctypes.c_ulong()
        try:
            while not self._stop.is_set():
                ok = kernel32.ReadDirectoryChangesW(
                    handle, ctypes.byref(buffer), ctypes.sizeof(buffer), True,
                    notify_filter, ctypes.byref(bytes_returned), None, None,
                )
                if not ok:
                    if self._stop.is_set():
                        break
                    raise ctypes.WinError()
                changed = self._parse_windows_events(buffer.raw[:bytes_returned.value])
                if changed:
                    time.sleep(self.debounce)
                    for path in changed:
                        self._diff_path(path)
        finally:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
            self._handle = None
    def _parse_windows_events(self, payload):
        changed = set()
        offset = 0
        length = len(payload)
        while offset + 12 <= length:
            next_offset, action, name_length = struct.unpack_from("<III", payload, offset)
            start = offset + 12
            end = start + name_length
            if end > length:
                break
            name = payload[start:end].decode("utf-16-le", errors="replace")
            if name:
                path = (self.root / name).resolve()
                try:
                    path.relative_to(self.root)
                except ValueError:
                    path = None
                if path is not None and self._eligible(path):
                    changed.add(path)
            if next_offset == 0:
                break
            offset += next_offset
        return changed
