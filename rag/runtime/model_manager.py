"""Mutually exclusive local model activation for CodeBridge RAG — RAG-008-B

This phase deliberately implements only initial mutual exclusion

It does not implement idle timeout concurrency control structured failure policy or hybrid execution
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol


class ManagedModel(str, Enum):
    TEXT = "TEXT"
    CODE = "CODE"


class ManagedRuntime(Protocol):
    def load(self, **kwargs: Any) -> Any:
        ...

    def unload(self, **kwargs: Any) -> Any:
        ...


@dataclass(frozen=True)
class ModelManagerSnapshot:
    active_model: Optional[ManagedModel]
    text_loaded: bool
    code_loaded: bool

    def __post_init__(self) -> None:
        if self.text_loaded and self.code_loaded:
            raise ValueError("text and code models cannot be resident together")
        if self.active_model is ManagedModel.TEXT and not self.text_loaded:
            raise ValueError("TEXT active_model requires text_loaded")
        if self.active_model is ManagedModel.CODE and not self.code_loaded:
            raise ValueError("CODE active_model requires code_loaded")
        if self.active_model is None and (self.text_loaded or self.code_loaded):
            raise ValueError("resident model requires active_model")


class ExclusiveModelManager:
    """Coordinates one text runtime and one code runtime

    Switching models always unloads the currently active runtime before loading
    the requested runtime

    The manager intentionally has no locks and no timeout policy in RAG-008-B
    """

    def __init__(
        self,
        *,
        text_runtime: ManagedRuntime,
        code_runtime: ManagedRuntime,
    ) -> None:
        if text_runtime is code_runtime:
            raise ValueError("text_runtime and code_runtime must be distinct")
        self._text_runtime = text_runtime
        self._code_runtime = code_runtime
        self._active_model: Optional[ManagedModel] = None

    @property
    def active_model(self) -> Optional[ManagedModel]:
        return self._active_model

    def snapshot(self) -> ModelManagerSnapshot:
        return ModelManagerSnapshot(
            active_model=self._active_model,
            text_loaded=self._active_model is ManagedModel.TEXT,
            code_loaded=self._active_model is ManagedModel.CODE,
        )

    def activate(
        self,
        model: ManagedModel,
        *,
        load_kwargs: Optional[dict[str, Any]] = None,
        unload_kwargs: Optional[dict[str, Any]] = None,
    ) -> Any:
        if not isinstance(model, ManagedModel):
            raise ValueError("model must be ManagedModel")

        load_args = dict(load_kwargs or {})
        unload_args = dict(unload_kwargs or {})

        if self._active_model is model:
            runtime = self._runtime_for(model)
            return runtime.load(**load_args)

        if self._active_model is not None:
            current = self._runtime_for(self._active_model)
            current.unload(**unload_args)
            self._active_model = None

        target = self._runtime_for(model)

        try:
            result = target.load(**load_args)
        except Exception:
            self._active_model = None
            raise

        self._active_model = model
        return result

    def unload_active(
        self,
        *,
        unload_kwargs: Optional[dict[str, Any]] = None,
    ) -> Any:
        if self._active_model is None:
            return None

        unload_args = dict(unload_kwargs or {})
        active = self._active_model
        runtime = self._runtime_for(active)

        try:
            return runtime.unload(**unload_args)
        finally:
            self._active_model = None

    def _runtime_for(self, model: ManagedModel) -> ManagedRuntime:
        if model is ManagedModel.TEXT:
            return self._text_runtime
        if model is ManagedModel.CODE:
            return self._code_runtime
        raise ValueError("unsupported managed model")
