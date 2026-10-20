"""Explicit offline recovery archive for non-secret runtime metadata only."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

FILES = (
    "runtime/python/python313._pth",
    "requirements.txt",
    "version.json",
)


def prepare_runtime_recovery(install_root: Path, destination: Path,
                             *, create_archive: bool = False) -> dict:
    root = Path(install_root).resolve()
    target = Path(destination).absolute()
    items: dict[str, bytes] = {}
    if target.exists() or target.is_relative_to(root):
        return {"state": "INVALID_ARCHIVE_DESTINATION", "archive_created": False}
    for relative in FILES:
        file = root / relative
        if not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(root):
            return {"state": "RUNTIME_METADATA_MISSING", "archive_created": False}
        items[relative] = file.read_bytes()
    digests = {name: hashlib.sha256(data).hexdigest()
               for name, data in items.items()}
    if not create_archive:
        return {"state": "RECOVERY_DRY_RUN", "archive_created": False,
                "files": digests, "will_include_secrets": False}
    if not target.parent.is_dir():
        return {"state": "ARCHIVE_PARENT_MISSING", "archive_created": False}
    # Create a self-contained recovery archive without user config, keys or RAG data.
    with ZipFile(target, mode="x", compression=ZIP_DEFLATED) as archive:
        for name, content in items.items():
            archive.writestr(name, content)
        archive.writestr("SHA256.json", json.dumps(digests,sort_keys=True))
    return {"state": "RECOVERY_ARCHIVE_CREATED", "archive_created": True,
            "files": digests, "will_include_secrets": False}


def main() -> int:
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--install-root",type=Path,required=True)
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--create-archive",action="store_true")
    args=parser.parse_args()
    result=prepare_runtime_recovery(
        args.install_root,args.archive,create_archive=args.create_archive)
    print(json.dumps(result,sort_keys=True))
    return 0 if result["state"] in (
        "RECOVERY_DRY_RUN","RECOVERY_ARCHIVE_CREATED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
