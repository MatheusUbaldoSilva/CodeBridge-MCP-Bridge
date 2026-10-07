"""On-demand llama.cpp lifecycle for the Jina text model — RAG-006-C.

Importing this module is side-effect free. The model process is created only
when TextModelLifecycle.load() is called explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import socket
import subprocess
import time
from typing import Callable, IO, List, Optional, Sequence, Tuple
from urllib.request import urlopen

from .artifact_install import verify_model_artifact
from .backend_policy import SELECTED_TEXT_BACKEND


class ModelLifecycleState(str, Enum):
    UNLOADED = "UNLOADED"
    LOADING = "LOADING"
    READY = "READY"
    IDLE = "IDLE"
    UNLOADING = "UNLOADING"


class ModelLifecycleError(RuntimeError):
    pass


class ModelLoadError(ModelLifecycleError):
    pass


class ModelUnloadError(ModelLifecycleError):
    pass


class ModelLifecycleStateError(ModelLifecycleError):
    pass


@dataclass(frozen=True)
class LlamaServerConfig:
    executable_path: Path
    model_path: Path
    host: str = "127.0.0.1"
    port: int = 0
    gpu_layers: int = 99
    device: Optional[str] = None
    pooling: str = "last"
    health_path: str = "/health"
    log_path: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.host != "127.0.0.1":
            raise ValueError(
                "RAG text model server must bind to 127.0.0.1"
            )
        if not isinstance(self.port, int) or isinstance(self.port, bool):
            raise ValueError("port must be an integer")
        if self.port < 0 or self.port > 65535:
            raise ValueError("port must be between 0 and 65535")
        if not isinstance(self.gpu_layers, int) or isinstance(
            self.gpu_layers,
            bool,
        ):
            raise ValueError("gpu_layers must be an integer")
        if self.gpu_layers < 0:
            raise ValueError("gpu_layers must be >= 0")
        if self.device is not None:
            if (
                not isinstance(self.device, str)
                or not self.device.strip()
            ):
                raise ValueError(
                    "device must be a non-empty string when provided"
                )
            if (
                self.device == "none"
                and self.gpu_layers != 0
            ):
                raise ValueError(
                    "device none requires gpu_layers=0"
                )
        if self.pooling != "last":
            raise ValueError("RAG-006-C requires last-token pooling")
        if not self.health_path.startswith("/"):
            raise ValueError("health_path must start with /")


@dataclass(frozen=True)
class ModelLifecycleSnapshot:
    state: ModelLifecycleState
    pid: Optional[int]
    host: str
    port: Optional[int]
    health_url: Optional[str]
    executable_path: Path
    model_path: Path
    process_alive: bool


ProcessFactory = Callable[..., subprocess.Popen]
HealthProbe = Callable[[str, float], bool]
Clock = Callable[[], float]
Sleeper = Callable[[float], None]


def find_free_loopback_port() -> int:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def probe_http_health(
    url: str,
    timeout_seconds: float,
) -> bool:
    try:
        with urlopen(
            url,
            timeout=timeout_seconds,
        ) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            return int(status) == 200
    except Exception:
        return False


def build_llama_server_argv(
    config: LlamaServerConfig,
    *,
    resolved_port: int,
) -> Tuple[str, ...]:
    if resolved_port < 1 or resolved_port > 65535:
        raise ValueError(
            "resolved_port must be between 1 and 65535"
        )

    argv = [
        str(config.executable_path),
        "-m",
        str(config.model_path),
        "--embedding",
        "--pooling",
        config.pooling,
        "--host",
        config.host,
        "--port",
        str(resolved_port),
    ]
    if config.device is not None:
        argv.extend(
            (
                "--device",
                config.device,
            )
        )
    argv.extend(
        (
            "-ngl",
            str(config.gpu_layers),
        )
    )
    return tuple(argv)


class TextModelLifecycle:
    def __init__(
        self,
        config: LlamaServerConfig,
        *,
        process_factory: ProcessFactory = subprocess.Popen,
        health_probe: HealthProbe = probe_http_health,
        clock: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
        port_allocator: Callable[[], int] = find_free_loopback_port,
    ) -> None:
        if not isinstance(config, LlamaServerConfig):
            raise ValueError("config must be LlamaServerConfig")

        self._config = config
        self._process_factory = process_factory
        self._health_probe = health_probe
        self._clock = clock
        self._sleeper = sleeper
        self._port_allocator = port_allocator

        self._state = ModelLifecycleState.UNLOADED
        self._history: List[ModelLifecycleState] = [
            ModelLifecycleState.UNLOADED
        ]
        self._process: Optional[subprocess.Popen] = None
        self._resolved_port: Optional[int] = None
        self._log_handle: Optional[IO[bytes]] = None

    @property
    def state(self) -> ModelLifecycleState:
        return self._state

    @property
    def state_history(self) -> Tuple[ModelLifecycleState, ...]:
        return tuple(self._history)

    def _transition(
        self,
        state: ModelLifecycleState,
    ) -> None:
        self._state = state
        self._history.append(state)

    def _process_alive(self) -> bool:
        return (
            self._process is not None
            and self._process.poll() is None
        )

    def _health_url(self) -> Optional[str]:
        if self._resolved_port is None:
            return None
        return (
            f"http://{self._config.host}:"
            f"{self._resolved_port}"
            f"{self._config.health_path}"
        )

    def snapshot(self) -> ModelLifecycleSnapshot:
        return ModelLifecycleSnapshot(
            state=self._state,
            pid=(
                int(self._process.pid)
                if self._process is not None
                else None
            ),
            host=self._config.host,
            port=self._resolved_port,
            health_url=self._health_url(),
            executable_path=self._config.executable_path,
            model_path=self._config.model_path,
            process_alive=self._process_alive(),
        )

    def _validate_runtime_inputs(self) -> None:
        if not self._config.executable_path.is_file():
            raise ModelLoadError(
                "llama-server executable does not exist"
            )

        verification = verify_model_artifact(
            self._config.model_path,
            SELECTED_TEXT_BACKEND.artifact_pin,
        )
        if not verification.valid:
            raise ModelLoadError(
                "text model artifact is missing or failed pinned verification"
            )

    def _open_log(self) -> IO[bytes]:
        path = self._config.log_path
        if path is None:
            if os.environ.get("LOCALAPPDATA"):
                root = Path(os.environ["LOCALAPPDATA"])
            else:
                root = self._config.model_path.parent
            path = (
                root
                / "CodeBridge"
                / "logs"
                / "rag"
                / "jina-v5-text-small"
                / "llama-server.log"
            )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        return path.open("ab", buffering=0)

    def _creation_flags(self) -> int:
        if os.name != "nt":
            return 0
        return int(
            getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            )
        )

    def load(
        self,
        *,
        timeout_seconds: float = 90.0,
        poll_interval_seconds: float = 0.20,
        health_timeout_seconds: float = 1.0,
    ) -> ModelLifecycleSnapshot:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be > 0"
            )
        if health_timeout_seconds <= 0:
            raise ValueError(
                "health_timeout_seconds must be > 0"
            )

        if self._state is ModelLifecycleState.READY:
            if not self._process_alive():
                self._reset_after_process_exit()
                raise ModelLoadError(
                    "model process exited after reaching READY"
                )
            return self.snapshot()

        if self._state is ModelLifecycleState.IDLE:
            if not self._process_alive():
                self._reset_after_process_exit()
                raise ModelLoadError(
                    "model process exited while IDLE"
                )
            self._transition(ModelLifecycleState.READY)
            return self.snapshot()

        if self._state is not ModelLifecycleState.UNLOADED:
            raise ModelLifecycleStateError(
                f"cannot load from state {self._state.value}"
            )

        self._validate_runtime_inputs()

        port = (
            self._config.port
            if self._config.port
            else int(self._port_allocator())
        )
        if port < 1 or port > 65535:
            raise ModelLoadError(
                "port allocator returned an invalid port"
            )

        self._resolved_port = port
        self._transition(ModelLifecycleState.LOADING)
        self._log_handle = self._open_log()

        argv = build_llama_server_argv(
            self._config,
            resolved_port=port,
        )

        try:
            self._process = self._process_factory(
                list(argv),
                stdin=subprocess.DEVNULL,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                shell=False,
                creationflags=self._creation_flags(),
            )
        except Exception as exc:
            self._close_log()
            self._resolved_port = None
            self._transition(ModelLifecycleState.UNLOADED)
            raise ModelLoadError(
                f"failed to start llama-server: {exc}"
            ) from exc

        deadline = self._clock() + timeout_seconds
        health_url = self._health_url()
        assert health_url is not None

        try:
            while self._clock() < deadline:
                if not self._process_alive():
                    exit_code = self._process.poll()
                    raise ModelLoadError(
                        "llama-server exited before health became ready "
                        f"(exit_code={exit_code})"
                    )

                if self._health_probe(
                    health_url,
                    health_timeout_seconds,
                ):
                    self._transition(
                        ModelLifecycleState.READY
                    )
                    return self.snapshot()

                self._sleeper(
                    poll_interval_seconds
                )

            raise ModelLoadError(
                "timed out waiting for llama-server health"
            )
        except Exception:
            self._cleanup_failed_load()
            raise

    def mark_idle(self) -> ModelLifecycleSnapshot:
        if self._state is ModelLifecycleState.IDLE:
            return self.snapshot()
        if self._state is not ModelLifecycleState.READY:
            raise ModelLifecycleStateError(
                f"cannot mark idle from state {self._state.value}"
            )
        if not self._process_alive():
            self._reset_after_process_exit()
            raise ModelLifecycleStateError(
                "cannot mark idle because model process exited"
            )

        self._transition(ModelLifecycleState.IDLE)
        return self.snapshot()

    def mark_ready(self) -> ModelLifecycleSnapshot:
        if self._state is ModelLifecycleState.READY:
            return self.snapshot()
        if self._state is not ModelLifecycleState.IDLE:
            raise ModelLifecycleStateError(
                f"cannot mark ready from state {self._state.value}"
            )
        if not self._process_alive():
            self._reset_after_process_exit()
            raise ModelLifecycleStateError(
                "cannot mark ready because model process exited"
            )

        self._transition(ModelLifecycleState.READY)
        return self.snapshot()

    def unload(
        self,
        *,
        timeout_seconds: float = 10.0,
    ) -> ModelLifecycleSnapshot:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")

        if self._state is ModelLifecycleState.UNLOADED:
            return self.snapshot()

        if self._state not in (
            ModelLifecycleState.READY,
            ModelLifecycleState.IDLE,
        ):
            raise ModelLifecycleStateError(
                f"cannot unload from state {self._state.value}"
            )

        self._transition(ModelLifecycleState.UNLOADING)
        process = self._process

        try:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(
                        timeout=timeout_seconds,
                    )
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(
                            timeout=timeout_seconds,
                        )
                    except subprocess.TimeoutExpired as exc:
                        raise ModelUnloadError(
                            "llama-server did not exit after kill"
                        ) from exc
        finally:
            self._process = None
            self._resolved_port = None
            self._close_log()

        self._transition(ModelLifecycleState.UNLOADED)
        return self.snapshot()

    def _cleanup_failed_load(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2.0)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=2.0)
                except Exception:
                    pass

        self._process = None
        self._resolved_port = None
        self._close_log()
        if self._state is not ModelLifecycleState.UNLOADED:
            self._transition(ModelLifecycleState.UNLOADED)

    def _reset_after_process_exit(self) -> None:
        self._process = None
        self._resolved_port = None
        self._close_log()
        if self._state is not ModelLifecycleState.UNLOADED:
            self._transition(ModelLifecycleState.UNLOADED)

    def _close_log(self) -> None:
        if self._log_handle is not None:
            try:
                self._log_handle.close()
            finally:
                self._log_handle = None
