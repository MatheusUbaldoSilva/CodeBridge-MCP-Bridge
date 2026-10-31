"""DQ-E-D-3C-E-1: deterministic Qdrant file-tree receipt in scratch only.

This is a bounded CONTENT check for synthetic data, not a Qdrant transactional
snapshot or an attestation that a parent process remains alive.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import stat

from rag.runtime.knowledge_deletion_bounded_catalog_lab import _validated_scratch_catalog
from rag.runtime.knowledge_deletion_pin_ipc_lab import (
    PrivateReadPinEnvelopeV1, PinEnvelopeLabError,
    verify_private_pin_envelope_lab,
)


class VectorTreeReceiptLabError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VectorFileReceiptLab:
    relative_path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class VectorTreeReceiptLab:
    schema_version: int
    project_id: str
    generation_id: str
    catalog_sha256: str
    nonce: str
    files: tuple[VectorFileReceiptLab, ...]
    directories: tuple[str, ...]
    tree_sha256: str


_MAX_FILES = 256
_MAX_TOTAL = 16 * 1024 * 1024
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _unsafe(path: Path) -> bool:
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        return True
    try:
        mode = path.lstat()
    except OSError as exc:
        raise VectorTreeReceiptLabError("scratch vector path unavailable") from exc
    return bool(getattr(mode, "st_file_attributes", 0) & _REPARSE)


def _fingerprint_tree(root: Path) -> tuple[tuple[VectorFileReceiptLab, ...], tuple[str, ...], str]:
    if _unsafe(root) or not root.is_dir():
        raise VectorTreeReceiptLabError("scratch vector root redirected or missing")
    base = root.resolve(strict=True)
    entries: list[VectorFileReceiptLab] = []
    directories: list[str] = []
    total = 0
    seen_casefold: set[str] = set()

    def visit(directory: Path) -> None:
        nonlocal total
        # scandir does not follow directory symlinks, and we reject any
        # reparse points (including junctions) before visiting children.
        if _unsafe(directory) or not directory.is_dir():
            raise VectorTreeReceiptLabError("redirected scratch vector directory")
        try:
            children = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            raise VectorTreeReceiptLabError("cannot list scratch vector tree") from exc
        for child in children:
            if _unsafe(child):
                raise VectorTreeReceiptLabError("redirected scratch vector file")
            resolved = child.resolve(strict=True)
            if not resolved.is_relative_to(base):
                raise VectorTreeReceiptLabError("vector entry escaped scratch root")
            relative = child.relative_to(root).as_posix()
            if relative.casefold() in seen_casefold:
                raise VectorTreeReceiptLabError("duplicate case-folded vector path")
            seen_casefold.add(relative.casefold())
            if child.is_dir():
                directories.append(relative)
                visit(child)
                continue
            before = child.lstat()
            if not stat.S_ISREG(before.st_mode):
                raise VectorTreeReceiptLabError("special file in vector tree")
            if len(entries) >= _MAX_FILES or total + before.st_size > _MAX_TOTAL:
                raise VectorTreeReceiptLabError("scratch vector limits exceeded")
            digest = sha256()
            try:
                with child.open("rb") as stream:
                    while block := stream.read(128 * 1024):
                        digest.update(block)
            except OSError as exc:
                raise VectorTreeReceiptLabError("cannot read scratch vector file") from exc
            after = child.lstat()
            if (after.st_size != before.st_size
                    or after.st_mtime_ns != before.st_mtime_ns
                    or (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
                    or _unsafe(child)):
                raise VectorTreeReceiptLabError("vector file changed during hashing")
            total += before.st_size
            entries.append(VectorFileReceiptLab(relative, before.st_size, digest.hexdigest()))

    visit(root)
    entries.sort(key=lambda e: e.relative_path)
    directories.sort()
    payload = {
        "directories":directories,
        "files":[[e.relative_path, e.size, e.sha256] for e in entries],
    }
    tree_hash = sha256(json.dumps(
        payload, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    return tuple(entries), tuple(directories), tree_hash


def create_vector_tree_receipt_lab(
    pin: PrivateReadPinEnvelopeV1, *, catalog_file: Path,
    laboratory_mode: bool = False,
) -> VectorTreeReceiptLab:
    if laboratory_mode is not True:
        raise PermissionError("scratch vector fingerprint requires lab mode")
    if type(pin) is not PrivateReadPinEnvelopeV1:
        raise VectorTreeReceiptLabError("immutable pin envelope required")
    verify_private_pin_envelope_lab(pin, catalog_file=catalog_file, laboratory_mode=True)
    _, scratch = _validated_scratch_catalog(catalog_file)
    qdrant = scratch / "generations" / pin.generation_id / "qdrant"
    files, directories, digest = _fingerprint_tree(qdrant)
    # The receipt is only accepted if the parent generation still matches.
    verify_private_pin_envelope_lab(pin, catalog_file=catalog_file, laboratory_mode=True)
    return VectorTreeReceiptLab(
        schema_version=1,
        project_id=pin.project_id,
        generation_id=pin.generation_id,
        catalog_sha256=pin.catalog_sha256,
        nonce=pin.nonce,
        files=files, directories=directories, tree_sha256=digest,
    )


def verify_vector_tree_receipt_lab(
    receipt: VectorTreeReceiptLab, pin: PrivateReadPinEnvelopeV1, *,
    catalog_file: Path, laboratory_mode: bool = False,
) -> dict:
    if laboratory_mode is not True:
        raise PermissionError("scratch vector verification requires lab mode")
    if (type(receipt) is not VectorTreeReceiptLab
            or type(pin) is not PrivateReadPinEnvelopeV1
            or receipt.schema_version != 1
            or (receipt.project_id, receipt.generation_id,
                receipt.catalog_sha256, receipt.nonce)
            != (pin.project_id, pin.generation_id, pin.catalog_sha256, pin.nonce)):
        raise VectorTreeReceiptLabError("vector receipt identity mismatch")
    observed = create_vector_tree_receipt_lab(
        pin,catalog_file=catalog_file,laboratory_mode=True,
    )
    if (receipt.files != observed.files
            or receipt.directories != observed.directories
            or receipt.tree_sha256 != observed.tree_sha256):
        raise VectorTreeReceiptLabError("pinned Qdrant tree fingerprint drift")
    return {
        "state":"LAB_VECTOR_TREE_CONTENT_VERIFIED",
        "generation_id":pin.generation_id,
        "tree_sha256":receipt.tree_sha256,
        "file_count":len(receipt.files),
        "parent_lock_attested":False,
        "activation_authorized":False,
        "operational_use_allowed":False,
    }