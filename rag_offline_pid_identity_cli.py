"""Read-only external PID audit; non-authorizing by construction."""
import json
import sys
from rag.runtime.offline_pid_identity_audit import inspect_process_identities


def main():
    result = inspect_process_identities()
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    sys.exit(main())
