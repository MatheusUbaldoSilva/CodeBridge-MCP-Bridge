import hashlib
import os
import subprocess
from pathlib import Path

from constants import APP_NAME, APP_VERSION


READ_ONLY_BATCH_KINDS = frozenset({
    "GIT_STATUS",
    "GIT_HEAD",
    "GIT_BRANCH",
    "VERSION",
    "FILE_STAT",
    "SHA256",
})
READ_ONLY_BATCH_MAX_ITEMS = 32
READ_ONLY_BATCH_MAX_PATH_CHARS = 4096
READ_ONLY_BATCH_MAX_ID_CHARS = 128
READ_ONLY_BATCH_MAX_GIT_OUTPUT_CHARS = 262144
READ_ONLY_BATCH_MAX_HASH_BYTES = 1073741824


class ReadOnlyBatchValidationError(ValueError):
    pass


def _normalize_kind(value):
    kind = str(value or "").strip().upper()
    if kind not in READ_ONLY_BATCH_KINDS:
        raise ReadOnlyBatchValidationError(
            f"kind nao permitido: {kind or '<vazio>'}"
        )
    return kind


def _validate_operations(operations):
    if not isinstance(operations, list):
        raise ReadOnlyBatchValidationError(
            "operations deve ser uma lista"
        )
    if not operations:
        raise ReadOnlyBatchValidationError(
            "operations nao pode ser vazia"
        )
    if len(operations) > READ_ONLY_BATCH_MAX_ITEMS:
        raise ReadOnlyBatchValidationError(
            f"maximo de {READ_ONLY_BATCH_MAX_ITEMS} operacoes"
        )

    validated = []
    for index, raw in enumerate(operations):
        if not isinstance(raw, dict):
            raise ReadOnlyBatchValidationError(
                f"operations[{index}] deve ser objeto"
            )
        extra = set(raw) - {"id", "kind", "path"}
        if extra:
            raise ReadOnlyBatchValidationError(
                f"operations[{index}] campos nao permitidos: "
                + ", ".join(sorted(extra))
            )
        kind = _normalize_kind(raw.get("kind"))
        item_id = raw.get("id")
        if item_id is not None:
            item_id = str(item_id)
            if not item_id or len(item_id) > READ_ONLY_BATCH_MAX_ID_CHARS:
                raise ReadOnlyBatchValidationError(
                    f"operations[{index}] id invalido"
                )

        path = raw.get("path")
        if kind == "VERSION":
            if path not in (None, ""):
                raise ReadOnlyBatchValidationError(
                    f"operations[{index}] VERSION nao aceita path"
                )
            path = None
        else:
            if path is None or not str(path).strip():
                raise ReadOnlyBatchValidationError(
                    f"operations[{index}] {kind} exige path"
                )
            path = str(path)
            if len(path) > READ_ONLY_BATCH_MAX_PATH_CHARS:
                raise ReadOnlyBatchValidationError(
                    f"operations[{index}] path excede limite"
                )

        validated.append({
            "index": index,
            "id": item_id,
            "kind": kind,
            "path": path,
        })
    return validated


def _absolute_path(value):
    return Path(value).expanduser().absolute()


def _git_env():
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _git_run(cwd, args):
    repo = _absolute_path(cwd)
    if not repo.is_dir():
        raise NotADirectoryError(str(repo))
    command = [
        "git",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(repo),
        *args,
    ]
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
        env=_git_env(),
        shell=False,
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if len(stdout) > READ_ONLY_BATCH_MAX_GIT_OUTPUT_CHARS:
        raise RuntimeError("saida Git excede limite")
    if len(stderr) > READ_ONLY_BATCH_MAX_GIT_OUTPUT_CHARS:
        raise RuntimeError("stderr Git excede limite")
    if completed.returncode != 0:
        message = stderr.strip() or stdout.strip()
        raise RuntimeError(
            f"git exit {completed.returncode}: {message}"
        )
    return stdout


def _git_status(path):
    output = _git_run(
        path,
        ["status", "--porcelain=v1", "--branch"],
    )
    lines = output.splitlines()
    branch_line = lines[0] if lines and lines[0].startswith("## ") else None
    changes = lines[1:] if branch_line else lines
    return {
        "path": str(_absolute_path(path)),
        "branch_line": branch_line,
        "clean": len(changes) == 0,
        "change_count": len(changes),
        "changes": changes,
    }


def _git_head(path):
    value = _git_run(
        path,
        ["rev-parse", "--verify", "HEAD"],
    ).strip()
    return {
        "path": str(_absolute_path(path)),
        "head": value,
    }


def _git_branch(path):
    branch = _git_run(
        path,
        ["branch", "--show-current"],
    ).strip()
    detached = not bool(branch)
    if detached:
        branch = _git_run(
            path,
            ["rev-parse", "--abbrev-ref", "HEAD"],
        ).strip()
    return {
        "path": str(_absolute_path(path)),
        "branch": branch,
        "detached": detached,
    }


def _file_stat(path):
    target = _absolute_path(path)
    stat = target.lstat()
    return {
        "path": str(target),
        "exists": True,
        "is_file": target.is_file(),
        "is_dir": target.is_dir(),
        "is_symlink": target.is_symlink(),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "mode": int(stat.st_mode),
    }


def _sha256(path):
    target = _absolute_path(path)
    stat = target.stat()
    if not target.is_file():
        raise ValueError("SHA256 exige arquivo regular")
    if stat.st_size > READ_ONLY_BATCH_MAX_HASH_BYTES:
        raise ValueError(
            "arquivo excede limite de 1 GiB para SHA256 em batch"
        )
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return {
        "path": str(target),
        "algorithm": "sha256",
        "sha256": digest.hexdigest(),
        "size": int(stat.st_size),
    }


def _execute_item(item):
    kind = item["kind"]
    path = item["path"]
    if kind == "VERSION":
        return {
            "app": APP_NAME,
            "version": APP_VERSION,
        }
    if kind == "GIT_STATUS":
        return _git_status(path)
    if kind == "GIT_HEAD":
        return _git_head(path)
    if kind == "GIT_BRANCH":
        return _git_branch(path)
    if kind == "FILE_STAT":
        return _file_stat(path)
    if kind == "SHA256":
        return _sha256(path)
    raise AssertionError(f"kind nao implementado: {kind}")


def execute_read_only_batch(operations):
    validated = _validate_operations(operations)
    items = []
    ok_count = 0
    for item in validated:
        base = {
            "index": item["index"],
            "id": item["id"],
            "kind": item["kind"],
            "ok": False,
            "result": None,
            "error_type": None,
            "error_message": None,
        }
        try:
            base["result"] = _execute_item(item)
            base["ok"] = True
            ok_count += 1
        except Exception as exc:
            base["error_type"] = type(exc).__name__
            base["error_message"] = str(exc)
        items.append(base)

    return {
        "count": len(items),
        "ok_count": ok_count,
        "error_count": len(items) - ok_count,
        "complete": True,
        "read_only": True,
        "items": items,
    }