import argparse
import json
import sys
from pathlib import Path

from client import BridgeClient, BridgeClientError


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def command_text(args):
    if getattr(args, "command", None) is not None:
        return args.command
    if getattr(args, "file", None) is not None:
        return Path(args.file).read_text(encoding="utf-8-sig")
    raise ValueError("informe --command ou --file")


def add_source(parser):
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--command")
    source.add_argument("--file")
    parser.add_argument("--target", required=True, choices=("POWERSHELL5.1", "POWERSHELL", "CMD", "SSH", "LINUX"))


def build_parser():
    parser = argparse.ArgumentParser(prog="codebridge-mcp")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    submit = sub.add_parser("submit")
    add_source(submit)
    run = sub.add_parser("run")
    add_source(run)
    run.add_argument("--timeout", type=float, default=60.0)
    approve = sub.add_parser("approve")
    approve.add_argument("job_id")
    result = sub.add_parser("result")
    result.add_argument("job_id")
    cancel = sub.add_parser("cancel")
    cancel.add_argument("job_id")
    sub.add_parser("stop")
    return parser


def main():
    args = build_parser().parse_args()
    client = BridgeClient()
    if args.action == "status":
        return emit(client.status())
    if args.action == "submit":
        return emit(client.submit(args.target, command_text(args)))
    if args.action == "approve":
        return emit(client.approve(args.job_id))
    if args.action == "result":
        return emit(client.get_job(args.job_id))
    if args.action == "cancel":
        return emit({"cancelled": client.cancel(args.job_id), "job_id": args.job_id})
    if args.action == "stop":
        return emit({"cancelled": client.stop()})
    if args.action == "run":
        result = client.run(args.target, command_text(args), timeout=args.timeout)
        emit(result)
        return 0 if result["state"] == "SUCCESS" else 2
    raise RuntimeError("acao desconhecida")


if __name__ == "__main__":
    try:
        code = main()
        if isinstance(code, int):
            raise SystemExit(code)
    except (BridgeClientError, TimeoutError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
