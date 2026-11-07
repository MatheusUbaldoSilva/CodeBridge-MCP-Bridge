"""Confianca na chave do servidor SSH (impressao digital / fingerprint).

Usa o mesmo known_hosts do OpenSSH (~/.ssh/known_hosts) que o terminal SSH
do CodeBridge ja le (load_system_host_keys + RejectPolicy). Aceitar uma
chave nova apenas ACRESCENTA uma linha; substituir uma chave que mudou
reescreve o arquivo guardando uma copia de seguranca antes.
"""
import base64
import hashlib
import os
import socket
import threading
from pathlib import Path

import paramiko
from paramiko.hostkeys import HostKeyEntry

TRUSTED = "TRUSTED"
UNKNOWN = "UNKNOWN"
CHANGED = "CHANGED"
BACKUP_SUFFIX = ".codebridge-bak"
_PREFERENCE = (
    "ssh-ed25519",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "ssh-rsa",
)
_lock = threading.Lock()


def known_hosts_path():
    return Path(os.path.expanduser("~")) / ".ssh" / "known_hosts"


def host_label(host, port=22):
    host = str(host or "").strip()
    port = int(port)
    if not host:
        raise ValueError("host SSH vazio")
    return host if port == 22 else f"[{host}]:{port}"


def fingerprint(key):
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _path(path):
    return Path(path) if path else known_hosts_path()


def known_keys(host, port=22, path=None):
    """Chaves ja confiadas para host:porta, como {tipo: PKey}."""
    target = _path(path)
    keys = paramiko.HostKeys()
    if target.is_file():
        keys.load(str(target))
    found = keys.lookup(host_label(host, port))
    if not found:
        return {}
    return {name: found[name] for name in found.keys()}


def preferred_types(known):
    """Pede ao servidor primeiro o tipo de chave que ja conhecemos."""
    for name in _PREFERENCE:
        if name in known:
            if name == "ssh-rsa":
                return ["rsa-sha2-512", "rsa-sha2-256", "ssh-rsa"]
            return [name]
    return [name for name in known]


def fetch_server_key(host, port=22, timeout=10, prefer=()):
    sock = socket.create_connection((str(host).strip(), int(port)), timeout=timeout)
    transport = paramiko.Transport(sock)
    try:
        if prefer:
            options = transport.get_security_options()
            available = list(options.key_types)
            first = [name for name in prefer if name in available]
            options.key_types = first + [n for n in available if n not in first]
        transport.banner_timeout = timeout
        transport.start_client(timeout=timeout)
        return transport.get_remote_server_key()
    finally:
        transport.close()
        try:
            sock.close()
        except OSError:
            pass


def describe(key, known):
    name = key.get_name()
    stored = known.get(name)
    if stored is not None:
        state = TRUSTED if stored.asbytes() == key.asbytes() else CHANGED
    elif known:
        # Ja conhecemos este servidor com outro tipo de chave e ele nao
        # apresentou nenhuma delas: tratamos como chave trocada.
        state = CHANGED
    else:
        state = UNKNOWN
    return {
        "key_type": name,
        "fingerprint": fingerprint(key),
        "key_base64": key.get_base64(),
        "state": state,
        "known_fingerprints": {
            kind: fingerprint(value) for kind, value in known.items()
        },
    }


def check(host, port=22, timeout=10, path=None, fetch=fetch_server_key):
    """Conecta so ate a troca de chaves (sem login) e compara a chave."""
    target = _path(path)
    known = known_keys(host, port, target)
    key = fetch(host, port, timeout, preferred_types(known))
    info = describe(key, known)
    info["host"] = str(host).strip()
    info["port"] = int(port)
    info["label"] = host_label(host, port)
    info["known_hosts"] = str(target)
    return info


def _matches(hostnames, label):
    for name in hostnames:
        if name.startswith("|1|"):
            try:
                if paramiko.HostKeys.hash_host(label, name) == name:
                    return True
            except Exception:
                continue
        elif name == label:
            return True
    return False


def _remove_host(path, label):
    if not path.is_file():
        return 0
    original = path.read_bytes()
    (path.parent / (path.name + BACKUP_SUFFIX)).write_bytes(original)
    kept = []
    removed = 0
    for line in original.decode("utf-8", errors="surrogateescape").splitlines(True):
        stripped = line.strip()
        entry = None
        if stripped and not stripped.startswith("#"):
            try:
                entry = HostKeyEntry.from_line(stripped)
            except Exception:
                entry = None
        if entry is not None and _matches(entry.hostnames, label):
            removed += 1
            continue
        kept.append(line)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes("".join(kept).encode("utf-8", errors="surrogateescape"))
    os.replace(temp, path)
    return removed


def _append(path, line):
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    if path.is_file() and path.stat().st_size:
        with open(path, "rb") as handle:
            handle.seek(-1, os.SEEK_END)
            if handle.read(1) != b"\n":
                prefix = "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(prefix + line)


def accept(host, port, expected_fingerprint, replace=False, timeout=10,
           path=None, fetch=fetch_server_key):
    """Grava a chave do servidor como confiavel.

    Busca a chave de novo e so grava se ela for exatamente a que a pessoa
    conferiu (expected_fingerprint). Chave trocada exige replace=True.
    """
    target = _path(path)
    info = check(host, port, timeout, target, fetch)
    if info["fingerprint"] != str(expected_fingerprint or "").strip():
        raise ValueError(
            "A chave do servidor mudou desde que voce conferiu. Confira de novo."
        )
    if info["state"] == TRUSTED:
        return info
    if info["state"] == CHANGED and not replace:
        raise PermissionError(
            "A chave do servidor e diferente da que estava salva. "
            "Substitua so se voce reinstalou ou trocou o servidor."
        )
    line = f"{info['label']} {info['key_type']} {info['key_base64']}\n"
    with _lock:
        if info["state"] == CHANGED:
            info["removed_entries"] = _remove_host(target, info["label"])
        _append(target, line)
    info["previous_state"] = info["state"]
    info["state"] = TRUSTED
    return info