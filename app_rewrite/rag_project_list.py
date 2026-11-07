"""Lista de projetos e selo RAG do painel de conhecimentos.

O projeto "codebridge" e a base principal herdada: continua existindo por
baixo, mas so aparece na lista quando tem documentos (ou quando nao ha
nenhum outro projeto). O selo descreve o projeto selecionado.
"""

MAIN_PROJECT = "codebridge"
SEP = " " + chr(0xB7) + " "


def _count(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def project_counts(data):
    counts = {}
    for item in (data or {}).get("projects") or []:
        pid = str(item.get("project_id") or "")
        if pid:
            counts[pid] = counts.get(pid, 0) + _count(item.get("document_count"))
    for item in (data or {}).get("isolated_project_indexes") or []:
        pid = str(item.get("project_id") or "")
        if pid and item.get("state") == "ISOLATED_READ_ONLY":
            counts[pid] = counts.get(pid, 0) + _count(item.get("document_count"))
    return counts


def visible_projects(data, registered=()):
    counts = project_counts(data)
    names = set(counts) | {str(n) for n in registered if n}
    names.discard(MAIN_PROJECT)
    if counts.get(MAIN_PROJECT, 0) > 0 or not names:
        names.add(MAIN_PROJECT)
    return sorted(names)


def _documents(n):
    return "1 documento" if n == 1 else f"{n} documentos"


def status_text(data, project_id):
    if not data:
        return "RAG: OFFLINE"
    pid = str(project_id or MAIN_PROJECT)
    count = project_counts(data).get(pid, 0)
    if pid == MAIN_PROJECT:
        state = str((data.get("index") or {}).get("state") or "").upper()
        if state not in ("READY", "EMPTY", ""):
            return "RAG: OFFLINE"
        if state != "READY":
            count = 0
    if count > 0:
        return "RAG: ONLINE" + SEP + pid + SEP + _documents(count)
    return "RAG: VAZIO" + SEP + pid + " ainda sem documentos"