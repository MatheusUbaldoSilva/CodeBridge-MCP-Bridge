"""DQ-E-D-1: immutable scratch private semantic parent/child pin envelope.

Strictly lab-only. Artifact and namespace verification is NOT proof that the
parent is still alive or that production locks are held in the child.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Any

from rag.runtime.knowledge_deletion_bounded_catalog_lab import (
    _validated_scratch_catalog,
)
from rag.runtime.knowledge_deletion_private_read_session_lab import PrivateLabPin


class PinEnvelopeLabError(RuntimeError):
    pass


_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_NAMESPACE = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")
_GENERATION = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{1,127}\Z")
_REVISION = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}\Z")


@dataclass(frozen=True, slots=True)
class PrivateReadPinEnvelopeV1:
    schema_version: int
    project_id: str
    generation_id: str
    source_revision: str
    catalog_sha256: str
    sqlite_sha256: str
    manifest_sha256: str
    nonce: str

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def parse(cls, payload: Any) -> "PrivateReadPinEnvelopeV1":
        if not isinstance(payload, dict) or set(payload) != set(cls.__dataclass_fields__):
            raise PinEnvelopeLabError("pin envelope fields must match exact schema")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise PinEnvelopeLabError("unsupported pin envelope version")
        for key, pattern in (
            ("project_id", _NAMESPACE),("generation_id",_GENERATION),
            ("source_revision",_REVISION),("catalog_sha256",_HEX64),
            ("sqlite_sha256",_HEX64),("manifest_sha256",_HEX64),("nonce",_HEX32),
        ):
            value = payload[key]
            if not isinstance(value, str) or pattern.fullmatch(value) is None:
                raise PinEnvelopeLabError(f"invalid pin envelope {key}")
        if payload["project_id"] == "codebridge":
            raise PinEnvelopeLabError("public project cannot use private lab pin")
        return cls(**payload)


def _sha(path: Path) -> str:
    if (not path.is_file() or path.is_symlink()
            or (hasattr(path, "is_junction") and path.is_junction())):
        raise PinEnvelopeLabError("missing or redirected scratch pin artifact")
    return sha256(path.read_bytes()).hexdigest()


def verify_private_pin_envelope_lab(
    envelope: PrivateReadPinEnvelopeV1, *, catalog_file: Path,
    laboratory_mode: bool = False,
) -> dict[str, Any]:
    """Verify fresh scratch file identity without obtaining ANY Win32 lock.

    Caller must retain generation->semantic->catalog locks for the entire IPC.
    The child cannot attest that this precondition is true.
    """
    if laboratory_mode is not True:
        raise PermissionError("explicit scratch lab mode required")
    if type(envelope) is not PrivateReadPinEnvelopeV1:
        raise PinEnvelopeLabError("typed immutable envelope required")
    envelope = PrivateReadPinEnvelopeV1.parse(envelope.to_payload())
    catalog, root = _validated_scratch_catalog(Path(catalog_file))
    # The parent refuses any unresolved journal. A detached child MUST fail
    # closed too: even a ROLLED_BACK journal requires explicit reconciliation.
    for journal in root.glob("rag-del-*.journal.json"):
        raise PinEnvelopeLabError("unreconciled scratch deletion journal")
    generations = root / "generations"
    if (generations.is_symlink()
            or (hasattr(generations,"is_junction") and generations.is_junction())):
        raise PinEnvelopeLabError("redirected scratch generations root")
    generation_dir = generations / envelope.generation_id
    if (not generation_dir.is_dir() or generation_dir.is_symlink()
            or (hasattr(generation_dir, "is_junction") and generation_dir.is_junction())
            or not generation_dir.resolve(strict=True).is_relative_to(root)):
        raise PinEnvelopeLabError("generation absent or redirected")
    db = generation_dir / "rag_index.sqlite3"
    manifest = generation_dir / "rag-index-manifest.json"
    catalog_raw = catalog.read_bytes()
    if sha256(catalog_raw).hexdigest() != envelope.catalog_sha256:
        raise PinEnvelopeLabError("catalog pin fingerprint mismatch")
    try:
        data = json.loads(catalog_raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise PinEnvelopeLabError("invalid pinned catalog JSON") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("projects"),dict):
        raise PinEnvelopeLabError("invalid pinned catalog schema")
    project = data["projects"].get(envelope.project_id)
    if (not isinstance(project,dict) or project.get("enabled") is not True
            or project.get("project_id") != envelope.project_id
            or project.get("source_revision") != envelope.source_revision
            or project.get("generation_directory") != str(generation_dir.resolve(strict=True))):
        raise PinEnvelopeLabError("generation or source revision not registered")
    for key, path, declared in (
        ("sqlite_sha256",db,envelope.sqlite_sha256),
        ("manifest_sha256",manifest,envelope.manifest_sha256),
    ):
        if _sha(path) != declared or project.get(key) != declared:
            raise PinEnvelopeLabError(f"{key} pin drift")
    # No model/Qdrant execution; prove SQLite can only be opened read-only.
    uri=db.resolve(strict=True).as_uri()+"?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=0.2)) as connection:
            connection.execute("PRAGMA query_only=ON")
            check=connection.execute("PRAGMA quick_check(1)").fetchone()
            if not check or check[0] != "ok":
                raise PinEnvelopeLabError("scratch SQLite integrity failed")
    except sqlite3.Error as exc:
        raise PinEnvelopeLabError("scratch SQLite cannot be verified read-only") from exc
    # Verify AGAIN after SQLite access; no assertion of lock or lifetime here.
    if (_sha(catalog) != envelope.catalog_sha256
            or _sha(db) != envelope.sqlite_sha256
            or _sha(manifest) != envelope.manifest_sha256):
        raise PinEnvelopeLabError("artifact drift during worker verification")
    if any(root.glob("rag-del-*.journal.json")):
        raise PinEnvelopeLabError("journal appeared during worker verification")
    return {
        "state": "LAB_PIN_ENVELOPE_VALIDATED",
        "project_id":envelope.project_id,
        "generation_id":envelope.generation_id,
        "nonce":envelope.nonce,
        "parent_locks_attested_by_worker":False,
        "operational_use_allowed":False,
        "activation_authorized":False,
    }


def envelope_from_private_lab_pin(
    pin: PrivateLabPin, *, catalog_file: Path,
    laboratory_mode: bool = False,
) -> PrivateReadPinEnvelopeV1:
    """Only create a pin while caller retains a semantic private session."""
    if laboratory_mode is not True:
        raise PermissionError("explicit scratch lab mode required")
    if (type(pin) is not PrivateLabPin or not pin._active[0]
            or not pin.semantic_lock_held):
        raise PinEnvelopeLabError("active semantic private session required")
    catalog, _ = _validated_scratch_catalog(Path(catalog_file))
    raw = catalog.read_bytes()
    try:
        row = json.loads(raw.decode("utf-8-sig"))["projects"][pin.project_id]
    except (KeyError,TypeError,ValueError,UnicodeError) as exc:
        raise PinEnvelopeLabError("missing pinned project catalog entry") from exc
    result = PrivateReadPinEnvelopeV1.parse({
        "schema_version":1,"project_id":pin.project_id,
        "generation_id":pin.generation,
        "source_revision":row.get("source_revision"),
        "catalog_sha256":sha256(raw).hexdigest(),
        "sqlite_sha256":_sha(pin.sqlite),
        "manifest_sha256":_sha(pin.manifest),
        "nonce":secrets.token_hex(16),
    })
    verify_private_pin_envelope_lab(result,catalog_file=catalog,laboratory_mode=True)
    return result