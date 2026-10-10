"""Lightweight project labels; never mutates production RAG indexes."""
import json
import os
import re
from pathlib import Path

_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
MAX_PREVIEW_FILES = 1200

def registry_path():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodeBridge" / "rag" / "ui-projects.json"

def list_projects():
    target = registry_path()
    if not target.exists():
        return []
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Invalid projects registry")
    return [x for x in data if isinstance(x, str) and _PATTERN.fullmatch(x) and "--" not in x]

def create_project(value):
    name = value.strip().lower()
    if not _PATTERN.fullmatch(name) or "--" in name:
        raise ValueError("Use letras minusculas, numeros e hifens (ate 64 caracteres).")
    names = list_projects()
    if name not in names:
        names.append(name)
        target = registry_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        try:
            with tmp.open("x", encoding="utf-8") as output:
                json.dump(sorted(names), output, ensure_ascii=False, indent=2)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
    return name

def validate_preview_folder(path):
    root = Path(path).resolve()
    if not root.is_dir():
        raise ValueError("Selecione uma pasta existente.")
    if any("codebridge_recovery" in part.lower() for part in root.parts):
        raise ValueError("A pasta de backup nao pode ser indexada. Escolha uma pasta de documentos.")
    seen = 0
    for base, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name.lower() not in {
            ".git", ".venv", "venv", "node_modules", "__pycache__", ".cache",
            "site-packages", "backups", "backup"
        }]
        seen += len(files)
        if seen > MAX_PREVIEW_FILES:
            raise ValueError(
                f"Pasta muito grande (mais de {MAX_PREVIEW_FILES} arquivos). "
                "Escolha uma pasta menor, especifica para conhecimentos.")
    return seen
