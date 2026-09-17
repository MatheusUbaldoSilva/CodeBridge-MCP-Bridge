import hashlib
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app_rewrite"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from credential_store import WindowsCredentialStore

TARGET = "CodeBridge-MCP-Bridge:MCP-Public"
USERNAME = "CodeBridge MCP Public Bearer"


def ensure_token():
    store = WindowsCredentialStore(target=TARGET)
    current = store.load()
    if current and current.get("password"):
        return current["password"]
    token = secrets.token_urlsafe(48)
    store.save(USERNAME, token)
    return token


def fingerprint(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def main():
    command = (sys.argv[1] if len(sys.argv) > 1 else "fingerprint").lower()
    token = ensure_token()
    if command == "ensure":
        print(token)
        return
    if command == "copy":
        subprocess.run(["clip.exe"], input=token, text=True, check=True)
        print("MCP_PUBLIC_TOKEN_COPIED")
        return
    if command == "fingerprint":
        print(fingerprint(token))
        return
    raise SystemExit("use: ensure | copy | fingerprint")


if __name__ == "__main__":
    main()
