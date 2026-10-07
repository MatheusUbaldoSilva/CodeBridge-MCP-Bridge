"""Local model manager for CodeBridge RAG — RAG-008-B/C/D/E

RAG-008-B establishes initial mutual exclusion between text and code models

RAG-008-C adds a configurable cooperative idle timeout

RAG-008-D serializes model state transitions so model loads cannot overlap

RAG-008-E adds MCP-safe structured operation results and lexical fallback signaling

Hybrid simultaneous residency remains out of scope
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import wraps
import threading
import time
from typing import Any, Callable, Optional, Protocol

from .query_classifier import QueryRoute


class ManagedModel(str, Enum):
    TEXT = "TEXT"
    CODE = "CODE"


class ModelManagerOperation(str, Enum):
    ACTIVATE = "ACTIVATE"
    UNLOAD = "UNLOAD"


class ModelManagerErrorType(str, Enum):
    ACTIVATION_FAILED = "ACTIVATION_FAILED"
    UNLOAD_FAILED = "UNLOAD_FAILED"


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


@dataclass(frozen=True)
class ModelManagerOperationResult:
    ok: bool
    operation: ModelManagerOperation
    requested_model: Optional[ManagedModel]
    active_model: Optional[ManagedModel]
    value: Any = None
    error_type: Optional[ModelManagerErrorType] = None
    error_message: Optional[str] = None
    cause_type: Optional[str] = None
    cleanup_errors: tuple[str, ...] = ()
    fallback_route: Optional[QueryRoute] = None

    def __post_init__(self) -> None:
        if not isinstance(self.operation, ModelManagerOperation):
            raise ValueError("operation must be ModelManagerOperation")
        if self.requested_model is not None and not isinstance(
            self.requested_model,
            ManagedModel,
        ):
            raise ValueError("requested_model must be ManagedModel when provided")
        if self.active_model is not None and not isinstance(
            self.active_model,
            ManagedModel,
        ):
            raise ValueError("active_model must be ManagedModel when provided")
        if self.ok:
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("successful result cannot contain an error")
            if self.fallback_route is not None:
                raise ValueError("successful result cannot request fallback")
        else:
            if not isinstance(self.error_type, ModelManagerErrorType):
                raise ValueError("failed result requires error_type")
            if not isinstance(self.error_message, str) or not self.error_message:
                raise ValueError("failed result requires error_message")
            if self.active_model is not None:
                raise ValueError("failed result cannot declare an active model")
            if self.fallback_route is not QueryRoute.LEXICAL_ONLY:
                raise ValueError("failed result must preserve lexical fallback")
        if any(not isinstance(item, str) or not item for item in self.cleanup_errors):
            raise ValueError("cleanup_errors must contain non-empty strings")

    @property
    def resources_released(self) -> bool:
        return not self.cleanup_errors


Clock = Callable[[], float]


def _serialized(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._operation_lock:
            return method(self, *args, **kwargs)

    return wrapper


class ExclusiveModelManager:
    """Coordinates one text runtime and one code runtime

    Switching models always unloads the currently active runtime before loading
    the requested runtime

    Idle timeout is cooperative in RAG-008-C
    callers explicitly invoke unload_if_idle instead of starting background threads
    """

    def __init__(
        self,
        *,
        text_runtime: ManagedRuntime,
        code_runtime: ManagedRuntime,
        idle_timeout_seconds: Optional[float] = None,
        clock: Clock = time.monotonic,
    ) -> None:
        if text_runtime is code_runtime:
            raise ValueError("text_runtime and code_runtime must be distinct")
        if idle_timeout_seconds is not None and float(idle_timeout_seconds) <= 0:
            raise ValueError("idle_timeout_seconds must be > 0 when configured")
        if not callable(clock):
            raise ValueError("clock must be callable")

        self._text_runtime = text_runtime
        self._code_runtime = code_runtime
        self._active_model: Optional[ManagedModel] = None
        self._idle_timeout_seconds = (
            None if idle_timeout_seconds is None else float(idle_timeout_seconds)
        )
        self._clock = clock
        self._last_activity_at: Optional[float] = None
        self._operation_lock = threading.RLock()

    @property
    @_serialized
    def active_model(self) -> Optional[ManagedModel]:
        return self._active_model

    @property
    def idle_timeout_seconds(self) -> Optional[float]:
        return self._idle_timeout_seconds

    @property
    @_serialized
    def last_activity_at(self) -> Optional[float]:
        return self._last_activity_at

    @_serialized
    def snapshot(self) -> ModelManagerSnapshot:
        return ModelManagerSnapshot(
            active_model=self._active_model,
            text_loaded=self._active_model is ManagedModel.TEXT,
            code_loaded=self._active_model is ManagedModel.CODE,
        )

    @_serialized
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
            result = runtime.load(**load_args)
            self._record_activity()
            return result

        if self._active_model is not None:
            current = self._runtime_for(self._active_model)
            current.unload(**unload_args)
            self._active_model = None
            self._last_activity_at = None

        target = self._runtime_for(model)

        try:
            result = target.load(**load_args)
        except Exception:
            self._active_model = None
            self._last_activity_at = None
            raise

        self._active_model = model
        self._record_activity()
        return result

    @_serialized
    def touch(self) -> float:
        if self._active_model is None:
            raise RuntimeError("cannot mark activity without an active model")
        return self._record_activity()

    @_serialized
    def idle_seconds(self, *, now: Optional[float] = None) -> Optional[float]:
        if self._active_model is None or self._last_activity_at is None:
            return None

        current = self._resolve_now(now)
        return max(0.0, current - self._last_activity_at)

    @_serialized
    def unload_if_idle(
        self,
        *,
        now: Optional[float] = None,
        unload_kwargs: Optional[dict[str, Any]] = None,
    ) -> bool:
        if self._idle_timeout_seconds is None:
            return False
        if self._active_model is None or self._last_activity_at is None:
            return False

        idle_for = self.idle_seconds(now=now)
        assert idle_for is not None

        if idle_for < self._idle_timeout_seconds:
            return False

        self.unload_active(unload_kwargs=unload_kwargs)
        return True

    @_serialized
    def unload_active(
        self,
        *,
        unload_kwargs: Optional[dict[str, Any]] = None,
    ) -> Any:
        if self._active_model is None:
            self._last_activity_at = None
            return None

        unload_args = dict(unload_kwargs or {})
        active = self._active_model
        runtime = self._runtime_for(active)

        try:
            return runtime.unload(**unload_args)
        finally:
            self._active_model = None
            self._last_activity_at = None

    @_serialized
    def activate_safe(
        self,
        model: ManagedModel,
        *,
        load_kwargs: Optional[dict[str, Any]] = None,
        unload_kwargs: Optional[dict[str, Any]] = None,
    ) -> ModelManagerOperationResult:
        if not isinstance(model, ManagedModel):
            raise ValueError("model must be ManagedModel")

        try:
            value = self.activate(
                model,
                load_kwargs=load_kwargs,
                unload_kwargs=unload_kwargs,
            )
        except Exception as exc:
            cleanup_errors = self._cleanup_all_runtimes(
                unload_kwargs=unload_kwargs,
            )
            return ModelManagerOperationResult(
                ok=False,
                operation=ModelManagerOperation.ACTIVATE,
                requested_model=model,
                active_model=None,
                error_type=ModelManagerErrorType.ACTIVATION_FAILED,
                error_message=str(exc) or type(exc).__name__,
                cause_type=type(exc).__name__,
                cleanup_errors=cleanup_errors,
                fallback_route=QueryRoute.LEXICAL_ONLY,
            )

        return ModelManagerOperationResult(
            ok=True,
            operation=ModelManagerOperation.ACTIVATE,
            requested_model=model,
            active_model=self._active_model,
            value=value,
        )

    @_serialized
    def unload_active_safe(
        self,
        *,
        unload_kwargs: Optional[dict[str, Any]] = None,
    ) -> ModelManagerOperationResult:
        requested = self._active_model

        try:
            value = self.unload_active(unload_kwargs=unload_kwargs)
        except Exception as exc:
            cleanup_errors = self._cleanup_all_runtimes(
                unload_kwargs=unload_kwargs,
            )
            return ModelManagerOperationResult(
                ok=False,
                operation=ModelManagerOperation.UNLOAD,
                requested_model=requested,
                active_model=None,
                error_type=ModelManagerErrorType.UNLOAD_FAILED,
                error_message=str(exc) or type(exc).__name__,
                cause_type=type(exc).__name__,
                cleanup_errors=cleanup_errors,
                fallback_route=QueryRoute.LEXICAL_ONLY,
            )

        return ModelManagerOperationResult(
            ok=True,
            operation=ModelManagerOperation.UNLOAD,
            requested_model=requested,
            active_model=None,
            value=value,
        )

    def _cleanup_all_runtimes(
        self,
        *,
        unload_kwargs: Optional[dict[str, Any]] = None,
    ) -> tuple[str, ...]:
        unload_args = dict(unload_kwargs or {})
        errors = []

        for label, runtime in (
            ("TEXT", self._text_runtime),
            ("CODE", self._code_runtime),
        ):
            try:
                runtime.unload(**unload_args)
            except Exception as exc:
                message = str(exc) or type(exc).__name__
                errors.append(
                    f"{label}:{type(exc).__name__}:{message}"
                )

        self._active_model = None
        self._last_activity_at = None
        return tuple(errors)

    def _record_activity(self) -> float:
        value = float(self._clock())
        self._last_activity_at = value
        return value

    def _resolve_now(self, now: Optional[float]) -> float:
        if now is None:
            return float(self._clock())
        return float(now)

    def _runtime_for(self, model: ManagedModel) -> ManagedRuntime:
        if model is ManagedModel.TEXT:
            return self._text_runtime
        if model is ManagedModel.CODE:
            return self._code_runtime
        raise ValueError("unsupported managed model")
