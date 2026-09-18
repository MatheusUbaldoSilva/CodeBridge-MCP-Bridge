import argparse
import ctypes
import json
import os
import sys
import time

from runtime import BridgeRuntime
from single_instance import SingleInstance


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate():
    script = os.path.abspath(__file__)
    params = " ".join([f'"{script}"'] + [f'"{arg}"' for arg in sys.argv[1:]])
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if result <= 32:
        raise RuntimeError(f"falha ao elevar processo: {result}")


def parse_args():
    parser = argparse.ArgumentParser(prog="CodeBridge-MCP-Bridge")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--no-elevate", action="store_true")
    return parser.parse_args()

def main():
    args = parse_args()
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "CodeBridge.MCPBridge.2"
        )
    except Exception:
        pass
    if not args.no_elevate and not is_admin():
        elevate()
        return 0
    instance = SingleInstance()
    if not instance.acquire():
        print("CodeBridge 2.0 ja esta em execucao")
        return 1
    runtime = BridgeRuntime()
    try:
        runtime.start()
        if args.probe:
            print(json.dumps(runtime.snapshot(), ensure_ascii=False, indent=2))
            return 0
        if args.headless:
            while True:
                time.sleep(1)
        from ui import run_ui
        return int(run_ui(runtime) or 0)
    except KeyboardInterrupt:
        return 0
    finally:
        runtime.stop()
        instance.release()


if __name__ == "__main__":
    raise SystemExit(main())
