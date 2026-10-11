"""Pure read-only presentation of incremental preview results.

This module cannot publish or modify an index.
"""
from __future__ import annotations

_STATUS = (
    ("new_files", "NOVO"),
    ("modified_files", "ATUALIZAR"),
    ("unchanged_files", "SEM ALTERACAO"),
    ("unknown_files", "VERIFICAR"),
)


def describe_incremental_preview(plan, assessment):
    if not isinstance(plan, dict) or not isinstance(assessment, dict):
        raise ValueError("preview requires plan and assessment")
    expected = plan.get("candidates")
    if not isinstance(expected, list):
        raise ValueError("missing candidates")
    paths = [item.get("path") for item in expected if isinstance(item, dict)]
    if len(paths) != len(expected) or any(not isinstance(p, str) or not p for p in paths):
        raise ValueError("invalid candidate paths")
    if len(set(paths)) != len(paths):
        raise ValueError("duplicate candidate paths")
    if assessment.get("project_id") != plan.get("project_id"):
        raise ValueError("project mismatch in preview")
    membership = {}
    for key, label in _STATUS:
        entries = assessment.get(key)
        if not isinstance(entries, list):
            raise ValueError("missing classification: " + key)
        for path in entries:
            if path not in paths or path in membership:
                raise ValueError("inconsistent candidate classification")
            membership[path] = label
    if set(membership) != set(paths):
        raise ValueError("unclassified candidate")
    for key, label in _STATUS:
        count_name = {"new_files": "new_count", "modified_files": "modified_count",
                      "unchanged_files": "unchanged_count", "unknown_files": "unknown_count"}[key]
        if assessment.get(count_name) != len(assessment[key]):
            raise ValueError("classification count mismatch")
    rows = [{"path": path, "status": membership[path]} for path in paths]
    counts = {label: len(assessment[key]) for key, label in _STATUS}
    # "safe_to_publish" is ignored: preview is always informational.
    return {
        "rows": rows,
        "summary": (
            f"{len(paths)} arquivos analisados: "
            f"{counts['NOVO']} novos, {counts['ATUALIZAR']} a atualizar, "
            f"{counts['SEM ALTERACAO']} sem alteracao, "
            f"{counts['VERIFICAR']} exigem verificacao. "
            f"{int(plan.get('denied_count') or 0)} protegidos; "
            f"{int(plan.get('unsupported_count') or 0)} nao suportados. "
            "Somente previa: nenhum arquivo foi indexado."
        ),
        "publish_enabled": False,
    }
