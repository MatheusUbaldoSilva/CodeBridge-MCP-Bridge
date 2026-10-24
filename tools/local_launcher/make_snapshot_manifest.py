"""Record a one-time, read-only integrity manifest for the local stable candidate."""
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

home = Path.home()
root = home / "CodeBridge-Stable"
manifest = home / "CodeBridge-Launcher" / "stable-manifest.json"
repository = home / "CodeBridge-MCP-Bridge"
if manifest.exists():
    raise SystemExit("REFUSING_TO_OVERWRITE_EXISTING_MANIFEST")
if not (root / "app_rewrite" / "main.py").is_file():
    raise SystemExit("INVALID_SNAPSHOT")
head = subprocess.check_output(
    ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
).strip()
entries = {}
for file in sorted(root.rglob("*")):
    if not file.is_file():
        continue
    if file.is_symlink():
        raise SystemExit("LINK_NOT_ALLOWED")
    rel = file.relative_to(root).as_posix()
    entries[rel] = hashlib.sha256(file.read_bytes()).hexdigest()
if len(entries) < 100:
    raise SystemExit("SNAPSHOT_UNEXPECTEDLY_SMALL")
data = {
    "state": "CANDIDATE",
    "promotion_authorized": False,
    "source_commit": head,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "checksums": entries,
}
manifest.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print("SNAPSHOT_MANIFEST_OK", head[:12], "files", len(entries))
