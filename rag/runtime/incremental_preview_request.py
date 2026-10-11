"""Pure guard against late or cancelled incremental preview results."""
from pathlib import Path


def matching_preview_request(request, revision, project, folder):
    if not isinstance(request, tuple) or len(request) != 3:
        return False
    if not isinstance(revision, int):
        return False
    if not isinstance(project, str) or not isinstance(folder, str) or not folder.strip():
        return False
    return (request[0] == revision and request[1] == project
            and request[2] == str(Path(folder).resolve()))
