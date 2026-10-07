"""GPU-first text model runtime with verified CPU fallback — RAG-006-F.

No hardware discovery or process creation happens on import.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
import re
import subprocess
from typing import Callable, Optional, Sequence, Tuple

from .lifecycle import (
    LlamaServerConfig,
    ModelLifecycleSnapshot,
    ModelLifecycleState,
    ModelLoadError,
    TextModelLifecycle,
)


class ModelExecutionMode(str, Enum):
    GPU = "GPU"
    CPU = "CPU"


class ModelFallbackError(RuntimeError):
    pass


class ModelFallbackExhaustedError(ModelFallbackError):
    def __init__(
        self,
        gpu_error: Optional[str],
        cpu_error: str,
    ) -> None:
        self.gpu_error = gpu_error
        self.cpu_error = cpu_error
        super().__init__(
            "text model failed on GPU and CPU fallback: "
            f"gpu={gpu_error!r}; cpu={cpu_error!r}"
        )


@dataclass(frozen=True)
class FallbackRuntimeSnapshot:
    lifecycle: ModelLifecycleSnapshot
    execution_mode: ModelExecutionMode
    fallback_used: bool
    gpu_error: Optional[str]
    selected_gpu_device: Optional[str]

    @property
    def state(self) -> ModelLifecycleState:
        return self.lifecycle.state

    @property
    def pid(self) -> Optional[int]:
        return self.lifecycle.pid

    @property
    def port(self) -> Optional[int]:
        return self.lifecycle.port


LifecycleFactory = Callable[
    [LlamaServerConfig],
    TextModelLifecycle,
]
DeviceRunner = Callable[..., subprocess.CompletedProcess]


_DEVICE_LINE = re.compile(
    r"^\s*([A-Za-z0-9_.:-]+):\s+.+$"
)


def discover_llama_devices(
    executable_path: Path,
    *,
    runner: DeviceRunner = subprocess.run,
    timeout_seconds: float = 10.0,
) -> Tuple[str, ...]:
    path = Path(executable_path)
    if not path.is_file():
        raise ModelFallbackError(
            "llama-server executable does not exist"
        )
    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be > 0"
        )

    try:
        completed = runner(
            [
                str(path),
                "--list-devices",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except Exception as exc:
        raise ModelFallbackError(
            f"failed to discover llama.cpp devices: {exc}"
        ) from exc

    if int(completed.returncode) != 0:
        raise ModelFallbackError(
            "llama.cpp device discovery failed "
            f"(exit_code={completed.returncode})"
        )

    devices = []
    for line in (
        (completed.stdout or "")
        + "\n"
        + (completed.stderr or "")
    ).splitlines():
        match = _DEVICE_LINE.match(line)
        if not match:
            continue
        name = match.group(1)
        if name not in devices:
            devices.append(name)

    return tuple(devices)


def build_cpu_fallback_config(
    config: LlamaServerConfig,
) -> LlamaServerConfig:
    if not isinstance(config, LlamaServerConfig):
        raise ValueError(
            "config must be LlamaServerConfig"
        )
    return replace(
        config,
        gpu_layers=0,
        device="none",
    )


def build_gpu_config(
    config: LlamaServerConfig,
    *,
    device: str,
) -> LlamaServerConfig:
    if not isinstance(config, LlamaServerConfig):
        raise ValueError(
            "config must be LlamaServerConfig"
        )
    if not isinstance(device, str) or not device.strip():
        raise ValueError(
            "device must be non-empty"
        )
    if device == "none":
        raise ValueError(
            "GPU device cannot be none"
        )

    gpu_layers = max(
        1,
        int(config.gpu_layers),
    )
    return replace(
        config,
        gpu_layers=gpu_layers,
        device=device,
    )


class TextModelFallbackManager:
    def __init__(
        self,
        *,
        gpu_config: Optional[LlamaServerConfig],
        cpu_config: LlamaServerConfig,
        selected_gpu_device: Optional[str] = None,
        lifecycle_factory: LifecycleFactory = TextModelLifecycle,
        gpu_unavailable_reason: Optional[str] = None,
    ) -> None:
        if gpu_config is not None:
            if gpu_config.device in (
                None,
                "none",
            ):
                raise ValueError(
                    "gpu_config must select an explicit GPU device"
                )
            if gpu_config.gpu_layers < 1:
                raise ValueError(
                    "gpu_config must offload at least one layer"
                )
        if not isinstance(
            cpu_config,
            LlamaServerConfig,
        ):
            raise ValueError(
                "cpu_config must be LlamaServerConfig"
            )
        if (
            cpu_config.device != "none"
            or cpu_config.gpu_layers != 0
        ):
            raise ValueError(
                "cpu_config must use device none and gpu_layers=0"
            )
        if (
            selected_gpu_device is not None
            and (
                not isinstance(
                    selected_gpu_device,
                    str,
                )
                or not selected_gpu_device.strip()
            )
        ):
            raise ValueError(
                "selected_gpu_device must be non-empty when provided"
            )

        self._gpu_config = gpu_config
        self._cpu_config = cpu_config
        self._selected_gpu_device = (
            selected_gpu_device
        )
        self._lifecycle_factory = (
            lifecycle_factory
        )
        self._gpu_unavailable_reason = (
            gpu_unavailable_reason
        )

        self._active_lifecycle: Optional[
            TextModelLifecycle
        ] = None
        self._execution_mode: Optional[
            ModelExecutionMode
        ] = None
        self._gpu_error: Optional[str] = None

    @classmethod
    def auto(
        cls,
        base_config: LlamaServerConfig,
        *,
        lifecycle_factory: LifecycleFactory = TextModelLifecycle,
        device_discovery: Callable[
            [Path],
            Sequence[str],
        ] = discover_llama_devices,
    ) -> "TextModelFallbackManager":
        devices = tuple(
            device_discovery(
                base_config.executable_path
            )
        )
        cpu_config = build_cpu_fallback_config(
            base_config
        )

        if devices:
            selected = str(devices[0])
            gpu_config = build_gpu_config(
                base_config,
                device=selected,
            )
            reason = None
        else:
            selected = None
            gpu_config = None
            reason = (
                "no llama.cpp GPU device discovered"
            )

        return cls(
            gpu_config=gpu_config,
            cpu_config=cpu_config,
            selected_gpu_device=selected,
            lifecycle_factory=lifecycle_factory,
            gpu_unavailable_reason=reason,
        )

    @property
    def active_lifecycle(
        self,
    ) -> TextModelLifecycle:
        if self._active_lifecycle is None:
            raise ModelFallbackError(
                "text model runtime is not loaded"
            )
        return self._active_lifecycle

    @property
    def execution_mode(
        self,
    ) -> Optional[ModelExecutionMode]:
        return self._execution_mode

    def _snapshot(
        self,
    ) -> FallbackRuntimeSnapshot:
        lifecycle = self.active_lifecycle
        mode = self._execution_mode
        assert mode is not None
        return FallbackRuntimeSnapshot(
            lifecycle=lifecycle.snapshot(),
            execution_mode=mode,
            fallback_used=(
                mode is ModelExecutionMode.CPU
            ),
            gpu_error=self._gpu_error,
            selected_gpu_device=(
                self._selected_gpu_device
            ),
        )

    def load(
        self,
        *,
        timeout_seconds: float = 90.0,
        poll_interval_seconds: float = 0.20,
        health_timeout_seconds: float = 1.0,
    ) -> FallbackRuntimeSnapshot:
        if self._active_lifecycle is not None:
            self._active_lifecycle.load(
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                health_timeout_seconds=health_timeout_seconds,
            )
            return self._snapshot()

        common = dict(
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            health_timeout_seconds=health_timeout_seconds,
        )

        if self._gpu_config is not None:
            gpu_lifecycle = self._lifecycle_factory(
                self._gpu_config
            )
            try:
                gpu_lifecycle.load(
                    **common
                )
            except ModelLoadError as exc:
                self._gpu_error = str(exc)
            else:
                self._active_lifecycle = (
                    gpu_lifecycle
                )
                self._execution_mode = (
                    ModelExecutionMode.GPU
                )
                self._gpu_error = None
                return self._snapshot()
        else:
            self._gpu_error = (
                self._gpu_unavailable_reason
                or "GPU unavailable"
            )

        cpu_lifecycle = self._lifecycle_factory(
            self._cpu_config
        )
        try:
            cpu_lifecycle.load(
                **common
            )
        except ModelLoadError as exc:
            cpu_error = str(exc)
            raise ModelFallbackExhaustedError(
                self._gpu_error,
                cpu_error,
            ) from exc

        self._active_lifecycle = cpu_lifecycle
        self._execution_mode = (
            ModelExecutionMode.CPU
        )
        return self._snapshot()

    def mark_idle(
        self,
    ) -> FallbackRuntimeSnapshot:
        self.active_lifecycle.mark_idle()
        return self._snapshot()

    def mark_ready(
        self,
    ) -> FallbackRuntimeSnapshot:
        self.active_lifecycle.mark_ready()
        return self._snapshot()

    def unload(
        self,
        *,
        timeout_seconds: float = 10.0,
    ) -> ModelLifecycleSnapshot:
        if self._active_lifecycle is None:
            return ModelLifecycleSnapshot(
                state=ModelLifecycleState.UNLOADED,
                pid=None,
                host=self._cpu_config.host,
                port=None,
                health_url=None,
                executable_path=self._cpu_config.executable_path,
                model_path=self._cpu_config.model_path,
                process_alive=False,
            )

        lifecycle = self._active_lifecycle
        try:
            return lifecycle.unload(
                timeout_seconds=timeout_seconds
            )
        finally:
            self._active_lifecycle = None
            self._execution_mode = None
