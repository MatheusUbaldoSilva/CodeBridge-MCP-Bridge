"""Read-only standalone Windows lab process observer. Never authorizes production."""
import argparse
import json
from rag.runtime.offline_scoped_cim_observer import observe_scoped_windows_pids

def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic PID observer (lab only)")
    parser.add_argument("--lab-only", action="store_true", required=True)
    parser.add_argument("--pid", action="append", type=int, required=True)
    args = parser.parse_args(argv)
    result = observe_scoped_windows_pids(args.pid)
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    # A successful lab observation must not be mistaken for a production gate.
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
