"""On-demand lifecycle for the pinned Jina Code GGUF — RAG-007-B."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .artifact_install import verify_model_artifact
from .code_backend_policy import (
    CODE_RECOMMENDED_CONTEXT_TOKENS,
    CODE_RECOMMENDED_UBATCH_SIZE,
    SELECTED_CODE_BACKEND,
)
from .lifecycle import (
    LlamaServerConfig,
    ModelLoadError,
    TextModelLifecycle,
)


def build_code_server_config(
    *,
    executable_path: Path,
    model_path: Path,
    port: int = 0,
    gpu_layers: int = 99,
    device: Optional[str] = None,
    context_size: int = CODE_RECOMMENDED_CONTEXT_TOKENS,
    ubatch_size: int = CODE_RECOMMENDED_UBATCH_SIZE,
    log_path: Optional[Path] = None,
) -> LlamaServerConfig:
    return LlamaServerConfig(
        executable_path=Path(executable_path),
        model_path=Path(model_path),
        host="127.0.0.1",
        port=port,
        gpu_layers=gpu_layers,
        device=device,
        context_size=context_size,
        ubatch_size=ubatch_size,
        pooling=SELECTED_CODE_BACKEND.pooling,
        health_path=SELECTED_CODE_BACKEND.health_endpoint,
        log_path=log_path,
    )


class CodeModelLifecycle(TextModelLifecycle):
    def _validate_runtime_inputs(self) -> None:
        if not self._config.executable_path.is_file():
            raise ModelLoadError(
                "llama-server executable does not exist"
            )

        verification = verify_model_artifact(
            self._config.model_path,
            SELECTED_CODE_BACKEND.artifact_pin,
        )
        if not verification.valid:
            raise ModelLoadError(
                "code model artifact is missing or failed pinned verification"
            )

    def _open_log(self):
        if self._config.log_path is not None:
            return super()._open_log()

        if os.environ.get("LOCALAPPDATA"):
            root = Path(os.environ["LOCALAPPDATA"])
        else:
            root = self._config.model_path.parent

        path = (
            root
            / "CodeBridge"
            / "logs"
            / "rag"
            / "jina-code-embeddings-1.5b"
            / "llama-server.log"
        )
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        return path.open("ab", buffering=0)
