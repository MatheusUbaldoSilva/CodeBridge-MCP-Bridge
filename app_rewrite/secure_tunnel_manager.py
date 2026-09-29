import ctypes
import os
import socket
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

import psutil

from config_store import ConfigStore
from dpapi_secret_store import DPAPISecretStore


_MIB_TCP_STATE_LISTEN = 2
_AF_INET = 2
_TCP_TABLE_OWNER_PID_LISTENER = 3


class _MIB_TCPROW_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("dwState", wintypes.DWORD),
        ("dwLocalAddr", wintypes.DWORD),
        ("dwLocalPort", wintypes.DWORD),
        ("dwRemoteAddr", wintypes.DWORD),
        ("dwRemotePort", wintypes.DWORD),
        ("dwOwningPid", wintypes.DWORD),
    ]


class SecureTunnelManager:
    MCP_URL = "http://127.0.0.1:8765/mcp"
    HEALTH_HOST = "127.0.0.1"
    HEALTH_PORT = 8080

    def __init__(self, config_store=None):
        self.root = Path(__file__).resolve().parent.parent
        local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        appdata = Path(os.environ.get("APPDATA", str(Path.home())))
        self.data_dir = local_appdata / "CodeBridge-MCP-Bridge"
        bundled_client = self.root / "tools" / "tunnel-client.exe"
        legacy_client = self.data_dir / "tools" / "tunnel-client.exe"
        self.client = bundled_client if bundled_client.is_file() else legacy_client
        self.config = config_store or ConfigStore()
        self._appdata = appdata
        self.secrets = DPAPISecretStore(
            self.data_dir / "secure_tunnel_runtime_key.dpapi"
        )
        self.tunnel_id = ""
        self.profile_name = "codebridge-local"
        self.profile = appdata / "tunnel-client" / f"{self.profile_name}.yaml"
        self._reload_company_config()
        self._process = None
        self._log_handle = None
        self._managed = False
        self._last_error = None
        self._recycled_pid = None

    @staticmethod
    def _legacy_tunnel_id(profile_path):
        try:
            text = Path(profile_path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line.startswith("tunnel_id:"):
                continue
            value = line.split(":", 1)[1].strip().strip('"').strip("'")
            if value.startswith("tunnel_"):
                return value
        return ""

    def _reload_company_config(self):
        company = self.config.load_company()
        if not company.get("tunnel_id"):
            legacy_profile = (
                self._appdata / "tunnel-client" / "codebridge-local.yaml"
            )
            legacy_id = self._legacy_tunnel_id(legacy_profile)
            if legacy_id:
                company = self.config.save_company(
                    company.get("company_name", ""),
                    legacy_id,
                    company.get("plugin_name") or "CodeBridge MCP",
                )
        self.tunnel_id = str(company.get("tunnel_id") or "").strip()
        self.profile_name = (
            str(company.get("profile_name") or "").strip() or "codebridge-local"
        )
        self.profile = (
            self._appdata / "tunnel-client" / f"{self.profile_name}.yaml"
        )
        return company

    @staticmethod
    def _process_running(process):
        return process is not None and process.poll() is None

    @staticmethod
    def _wait_for(predicate, timeout=15.0, interval=0.15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    @classmethod
    def _health_online(cls):
        try:
            with socket.create_connection(
                (cls.HEALTH_HOST, cls.HEALTH_PORT), timeout=0.25
            ):
                return True
        except OSError:
            return False

    def _allowed_client_paths(self):
        candidates = {
            self.client,
            self.root / "tools" / "tunnel-client.exe",
            self.data_dir / "tools" / "tunnel-client.exe",
        }
        result = set()
        for candidate in candidates:
            try:
                result.add(
                    os.path.normcase(
                        os.path.abspath(str(candidate))
                    )
                )
            except Exception:
                pass
        return result

    def _existing_tunnel_info(self, pid):
        if not pid:
            return None
        try:
            process = psutil.Process(int(pid))
            executable = os.path.normcase(
                os.path.abspath(process.exe())
            )
            cmdline = [
                str(part)
                for part in process.cmdline()
            ]
            parent_pid = int(process.ppid() or 0)
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            OSError,
            ValueError,
        ):
            return None

        normalized = [
            part.strip().lower()
            for part in cmdline
        ]
        profile_matches = False
        for index, part in enumerate(normalized):
            if part != "--profile":
                continue
            if index + 1 >= len(cmdline):
                continue
            if (
                str(cmdline[index + 1]).strip()
                == self.profile_name
            ):
                profile_matches = True
                break

        is_ours = bool(
            executable in self._allowed_client_paths()
            and "run" in normalized
            and profile_matches
        )
        parent_is_live_codebridge = False
        ancestor_pid = parent_pid
        for _ in range(4):
            if ancestor_pid <= 0:
                break
            try:
                parent = psutil.Process(ancestor_pid)
                parent_cmd = " ".join(
                    str(part)
                    for part in parent.cmdline()
                ).lower()
                if (
                    parent.is_running()
                    and "main.py" in parent_cmd
                    and "codebridge" in parent_cmd
                ):
                    parent_is_live_codebridge = True
                    break
                ancestor_pid = int(parent.ppid() or 0)
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                OSError,
            ):
                break

        return {
            "pid": int(pid),
            "executable": executable,
            "cmdline": cmdline,
            "parent_pid": parent_pid or None,
            "is_codebridge_tunnel": is_ours,
            "parent_is_live_codebridge": (
                parent_is_live_codebridge
            ),
        }

    @staticmethod
    def _terminate_pid(pid):
        process = psutil.Process(int(pid))
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except psutil.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def _recycle_inherited_tunnel(self):
        if not self._health_online():
            return True

        pid = self._health_listener_pid()
        info = self._existing_tunnel_info(pid)
        if not info or not info["is_codebridge_tunnel"]:
            self._last_error = (
                "Porta do Secure Tunnel ocupada por processo "
                "nao reconhecido; nenhuma finalizacao automatica "
                "foi executada"
            )
            return False

        if info["parent_is_live_codebridge"]:
            self._last_error = (
                "Secure Tunnel pertence a outra instancia ativa "
                "do CodeBridge; recuperacao automatica bloqueada"
            )
            return False

        try:
            self._terminate_pid(pid)
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.TimeoutExpired,
            OSError,
        ) as exc:
            self._last_error = (
                "Falha ao reciclar Secure Tunnel herdado: "
                f"{type(exc).__name__}: {exc}"
            )
            return False

        if not self._wait_for(
            lambda: not self._health_online(),
            timeout=6.0,
        ):
            self._last_error = (
                "Secure Tunnel herdado foi finalizado, mas "
                "a porta de health continuou ocupada"
            )
            return False

        self._recycled_pid = int(pid)
        return True

    @classmethod
    def _health_listener_pid(cls):
        if os.name != "nt":
            return None

        get_table = ctypes.windll.iphlpapi.GetExtendedTcpTable
        size = wintypes.ULONG(0)
        result = get_table(
            None,
            ctypes.byref(size),
            False,
            _AF_INET,
            _TCP_TABLE_OWNER_PID_LISTENER,
            0,
        )
        if result not in (0, 122):
            return None

        buffer = ctypes.create_string_buffer(size.value)
        result = get_table(
            buffer,
            ctypes.byref(size),
            False,
            _AF_INET,
            _TCP_TABLE_OWNER_PID_LISTENER,
            0,
        )
        if result != 0:
            return None

        count = ctypes.cast(
            buffer,
            ctypes.POINTER(wintypes.DWORD),
        ).contents.value
        row_size = ctypes.sizeof(_MIB_TCPROW_OWNER_PID)
        base = ctypes.addressof(buffer) + ctypes.sizeof(wintypes.DWORD)

        for index in range(count):
            row = _MIB_TCPROW_OWNER_PID.from_address(
                base + index * row_size
            )
            port = socket.ntohs(row.dwLocalPort & 0xFFFF)
            address = socket.inet_ntoa(
                int(row.dwLocalAddr).to_bytes(
                    4,
                    byteorder="little",
                )
            )
            if (
                row.dwState == _MIB_TCP_STATE_LISTEN
                and port == cls.HEALTH_PORT
                and address == cls.HEALTH_HOST
            ):
                return int(row.dwOwningPid)

        return None

    def _log_contains(self, marker):
        log_path = self.data_dir / "secure_tunnel.log"
        try:
            if not log_path.is_file():
                return False
            with open(log_path, "rb") as handle:
                handle.seek(max(0, log_path.stat().st_size - 131072))
                return marker.encode("utf-8") in handle.read()
        except OSError:
            return False

    def save_runtime_key(self, key):
        key = str(key or "").strip()
        if not key:
            raise ValueError("Runtime API key do Secure Tunnel nao pode ser vazia")
        if any(ch.isspace() for ch in key):
            raise ValueError(
                "Runtime API key invalida: contem espacos ou quebras de linha"
            )
        if len(key) < 20:
            raise ValueError("Runtime API key invalida: tamanho inesperado")
        return self.secrets.save(key)

    def credential_configured(self):
        try:
            return bool(self.secrets.exists() and self.secrets.load())
        except Exception:
            return False

    def _load_runtime_key(self):
        key = self.secrets.load()
        if not key:
            raise RuntimeError(
                "Runtime API key do Secure Tunnel nao configurada no armazenamento DPAPI"
            )
        return key

    def _open_log(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self._log_handle is None or self._log_handle.closed:
            self._log_handle = open(
                self.data_dir / "secure_tunnel.log",
                "a", encoding="utf-8", buffering=1,
            )
        return self._log_handle

    @staticmethod
    def _creationflags():
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def _profile_matches(self):
        try:
            if not self.profile.is_file():
                return False
            text = self.profile.read_text(encoding="utf-8", errors="ignore")
            return self.tunnel_id in text and self.MCP_URL in text
        except OSError:
            return False

    def prepare_profile(self):
        self._reload_company_config()
        if not self.tunnel_id:
            raise RuntimeError("Tunnel ID ainda nao configurado")
        if not self.client.is_file():
            raise FileNotFoundError(f"tunnel-client nao encontrado: {self.client}")
        key = self._load_runtime_key()
        env = os.environ.copy()
        env["CONTROL_PLANE_API_KEY"] = key
        log_handle = self._open_log()
        self._ensure_profile(env, log_handle)
        key = None
        return {
            "profile": self.profile_name,
            "profile_path": str(self.profile),
            "tunnel_id": self.tunnel_id,
            "mcp_url": self.MCP_URL,
        }

    def _ensure_profile(self, env, log_handle):
        if self._profile_matches():
            return
        self.profile.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.profile.unlink(missing_ok=True)
        except OSError:
            pass
        result = subprocess.run(
            [
                str(self.client), "init",
                "--sample", "sample_mcp_remote_no_auth",
                "--profile", self.profile_name,
                "--tunnel-id", self.tunnel_id,
                "--mcp-server-url", self.MCP_URL,
            ],
            cwd=str(self.root),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=self._creationflags(),
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"tunnel-client init falhou: exit {result.returncode}"
            )

    def _terminate(self):
        process = self._process
        if not self._process_running(process):
            return
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def start(self):
        self._reload_company_config()
        if self._process_running(self._process):
            return self.status()
        if not self.tunnel_id:
            self._managed = False
            self._last_error = (
                "Secure Tunnel nao configurado. Execute Configurar CodeBridge."
            )
            return self.status()
        if not self.credential_configured():
            self._managed = False
            self._last_error = (
                "API key do Secure Tunnel nao configurada. "
                "Execute Configurar CodeBridge."
            )
            return self.status()
        if self._health_online():
            self._managed = False
            if not self._recycle_inherited_tunnel():
                return self.status()
        if not self.client.is_file():
            self._last_error = f"tunnel-client nao encontrado: {self.client}"
            return self.status()

        key = None
        try:
            key = self._load_runtime_key()
            env = os.environ.copy()
            env["CONTROL_PLANE_API_KEY"] = key
            log_handle = self._open_log()
            self._ensure_profile(env, log_handle)
            self._process = subprocess.Popen(
                [str(self.client), "run", "--profile", self.profile_name],
                cwd=str(self.root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=env,
                creationflags=self._creationflags(),
            )
            if not self._wait_for(
                lambda: self._process_running(self._process)
                and self._health_online()
                and self._log_contains("tunnel-client started"),
                timeout=18.0,
            ):
                raise RuntimeError("Secure Tunnel nao ficou ONLINE")
            self._managed = True
            self._last_error = None
            return self.status()
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            self._terminate()
            self._process = None
            self._managed = False
            return self.status()
        finally:
            key = None

    def stop(self):
        self._terminate()
        self._process = None
        self._managed = False
        if self._log_handle is not None:
            try:
                self._log_handle.close()
            except Exception:
                pass
            self._log_handle = None
        return self.status()

    def status(self):
        self._reload_company_config()
        running = self._process_running(self._process)
        health = self._health_online()
        external_pid = (
            self._health_listener_pid()
            if health and not running
            else None
        )
        if running and health:
            state = "ONLINE"
        elif running:
            state = "STARTING"
        elif health:
            state = "ONLINE"
        elif not self.tunnel_id:
            state = "CONFIG_REQUIRED"
        else:
            state = "OFFLINE"
        return {
            "state": state,
            "managed_by_codebridge": bool(self._managed and running),
            "managed_pid": self._process.pid if running else None,
            "external_pid": external_pid,
            "external_process": bool(health and not running),
            "recycled_inherited_pid": self._recycled_pid,
            "health_online": bool(health),
            "credential_configured": self.credential_configured(),
            "client_available": self.client.is_file(),
            "profile_exists": self.profile.is_file(),
            "profile": self.profile_name,
            "tunnel_id": self.tunnel_id or None,
            "mcp_url": self.MCP_URL,
            "last_error": self._last_error,
        }
