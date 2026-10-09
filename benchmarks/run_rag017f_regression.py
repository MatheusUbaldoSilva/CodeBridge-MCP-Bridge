"""RAG-017-F: run full semantic regression without modifying frozen RAG-014 artifacts."""
from pathlib import Path
import importlib.util
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
source=ROOT/"benchmarks"/"run_rag014_semantic_benchmark.py"
spec=importlib.util.spec_from_file_location("rag017f_semantic",source)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
module.OUTPUT=ROOT/"benchmarks"/"rag017f_semantic_latest.json"
module.main()
