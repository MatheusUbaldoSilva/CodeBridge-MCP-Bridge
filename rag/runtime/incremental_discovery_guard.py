"""Read-only inventory guard for changes during RAG candidate discovery."""
from __future__ import annotations
import os
from pathlib import Path


def inventory_folder(folder):
    root = Path(folder).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("preview folder missing")
    inventory = {}
    for base, directories, filenames in os.walk(root, followlinks=False):
        base_path = Path(base)
        directories[:] = [name for name in directories
                          if not (base_path / name).is_symlink()]
        for name in filenames:
            file = base_path / name
            if file.is_symlink():
                continue
            try:
                info = file.stat()
            except OSError as exc:
                raise ValueError("file disappeared during discovery") from exc
            if not file.is_file():
                continue
            relative = file.relative_to(root).as_posix()
            inventory[relative] = (info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    return inventory


def assert_discovery_unchanged(initial, folder):
    if inventory_folder(folder) != initial:
        raise ValueError("folder changed during discovery; generate a new preview")
