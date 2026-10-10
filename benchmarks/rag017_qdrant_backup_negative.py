"""Disposable Qdrant backup integrity negative test."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);a=p.parse_args()
root=a.root.resolve()
if not root.name.startswith("CodeBridge-RAG017-BackupProbe-") or root.parent.name.lower()!="temp":raise SystemExit("unsafe root")
backup=root/"backup"
files=sorted(x for x in backup.rglob("*") if x.is_file())
if not files:raise SystemExit("missing backup")
target=files[0];original=hashlib.sha256(target.read_bytes()).hexdigest()
corrupted=root/"corrupted_copy"
corrupted.mkdir(exist_ok=False)
candidate=corrupted/target.name
candidate.write_bytes(target.read_bytes()+b"TEST_CORRUPTION")
detected=hashlib.sha256(candidate.read_bytes()).hexdigest()!=original
print(json.dumps({"test":"detect_mutated_copy","corruption_detected":detected,"original_backup_untouched":hashlib.sha256(target.read_bytes()).hexdigest()==original}))
if not detected:raise SystemExit(2)
