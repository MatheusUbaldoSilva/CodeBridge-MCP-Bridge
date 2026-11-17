"""Sincronizacao incremental de pastas do servidor Linux para o Windows.

Baixa (SFTP) apenas arquivos novos ou alterados -- compara tamanho e mtime --
de forma aditiva (nao apaga nada local por padrao). Reusa a conexao e as
credenciais do CodeBridge: host/porta de config.json e usuario/senha do
Windows Credential Manager (credential_store), abrindo a sessao com
ssh_transfer.connect_sftp. Os pares de sincronizacao ficam em
project-sync.json.

Objetivo: trazer projetos do servidor para uma pasta do Windows, para depois
indexar no RAG. A indexacao e um passo separado (esta versao so sincroniza e
reporta o que mudou).

A logica (config, varredura remota, decisao incremental) e pura e testavel com
um SFTP fake; a conexao real so e aberta quando nenhum sftp e injetado.
"""
import json
import os
import stat
import time
from pathlib import Path

APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodeBridge"
CONFIG_PATH = APP_DIR / "project-sync.json"
SSH_CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_INTERVAL_MIN = 10


def _now():
    return time.time()


# --------------------------------------------------------------------------
# config (project-sync.json)
# --------------------------------------------------------------------------
def load_config(path=None):
    p = Path(path) if path else CONFIG_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        data = {}
    pairs = data.get("pairs") if isinstance(data, dict) else None
    if not isinstance(pairs, list):
        pairs = []
    return {"pairs": pairs}


def save_config(cfg, path=None):
    p = Path(path) if path else CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _new_id(cfg):
    existentes = {p.get("id") for p in cfg["pairs"]}
    i = 1
    while f"sync{i}" in existentes:
        i += 1
    return f"sync{i}"


def add_pair(remote, local, project_id=None, interval_min=DEFAULT_INTERVAL_MIN,
             auto=False, index=False, mirror=False, path=None):
    cfg = load_config(path)
    pair = {
        "id": _new_id(cfg),
        "remote": str(remote),
        "local": str(local),
        "project_id": project_id,
        "interval_min": int(interval_min) if interval_min else DEFAULT_INTERVAL_MIN,
        "auto": bool(auto),
        "index": bool(index),
        "mirror": bool(mirror),
        "last_sync": None,
    }
    cfg["pairs"].append(pair)
    save_config(cfg, path)
    return pair


def remove_pair(pair_id, path=None):
    cfg = load_config(path)
    antes = len(cfg["pairs"])
    cfg["pairs"] = [p for p in cfg["pairs"] if p.get("id") != pair_id]
    save_config(cfg, path)
    return antes != len(cfg["pairs"])


def list_pairs(path=None):
    return load_config(path)["pairs"]


def _get_pair(pair_id, path=None):
    for p in list_pairs(path):
        if p.get("id") == pair_id:
            return p
    return None


def _update_pair(pair_id, changes, path=None):
    cfg = load_config(path)
    achou = None
    for p in cfg["pairs"]:
        if p.get("id") == pair_id:
            p.update(changes)
            achou = p
    save_config(cfg, path)
    return achou


def set_auto(pair_id, value, path=None):
    return _update_pair(pair_id, {"auto": bool(value)}, path)


def set_index(pair_id, value, path=None):
    return _update_pair(pair_id, {"index": bool(value)}, path)


# --------------------------------------------------------------------------
# conexao real (so quando nenhum sftp e injetado)
# --------------------------------------------------------------------------
def _default_connect(timeout=15):
    from ssh_transfer import connect_sftp
    from credential_store import WindowsCredentialStore
    ssh = json.loads(SSH_CONFIG_PATH.read_text(encoding="utf-8"))
    host = ssh.get("ssh_host")
    port = ssh.get("ssh_port", 22)
    creds = WindowsCredentialStore().load() or {}
    if not host or not creds.get("username"):
        raise RuntimeError(
            "Configuracao SSH incompleta (host/credenciais). "
            "Configure e salve no painel SSH do CodeBridge."
        )
    return connect_sftp(host, port, creds["username"],
                        creds.get("password", ""), timeout=timeout)


# --------------------------------------------------------------------------
# varredura remota + decisao incremental
# --------------------------------------------------------------------------
def _walk_remote(sftp, root):
    """Gera (relpath, remote_path, size, mtime) de cada ARQUIVO sob root."""
    pilha = [("", root)]
    while pilha:
        rel, remote_dir = pilha.pop()
        try:
            entries = sftp.listdir_attr(remote_dir)
        except IOError:
            continue
        for at in entries:
            nome = at.filename
            if nome in (".", ".."):
                continue
            rpath = (rel + "/" + nome) if rel else nome
            remote_path = remote_dir.rstrip("/") + "/" + nome
            if stat.S_ISDIR(at.st_mode):
                pilha.append((rpath, remote_path))
            elif stat.S_ISREG(at.st_mode):
                yield rpath, remote_path, int(at.st_size), int(at.st_mtime)


def _shq(s):
    return "'" + str(s).replace("'", "'\\''") + "'"


def _walk_remote_fast(client, root):
    """Varredura rapida: um unico 'find' no servidor, em vez de dir a dir."""
    root = str(root).rstrip("/")
    cmd = "find %s -type f -printf '%%P\\t%%s\\t%%T@\\n'" % _shq(root)
    _in, out, err = client.exec_command(cmd)
    data = out.read().decode("utf-8", "replace")
    status = out.channel.recv_exit_status()
    if status != 0:
        msg = err.read().decode("utf-8", "replace").strip()
        raise RuntimeError("find falhou (%d): %s" % (status, msg or "sem detalhe"))
    saida = []
    for line in data.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        rpath, size_s, mtime_s = parts
        try:
            size = int(size_s)
            mtime = int(float(mtime_s))
        except ValueError:
            continue
        saida.append((rpath, root + "/" + rpath, size, mtime))
    return saida


def _precisa_baixar(local_file, size, mtime):
    try:
        st = local_file.stat()
    except (FileNotFoundError, OSError):
        return True
    return not (st.st_size == size and int(st.st_mtime) >= mtime)


def sync_pair(pair, sftp=None, connector=None, max_files=None, client=None):
    """Baixa novos/alterados do remoto para o local (aditivo). Retorna resumo."""
    own = False
    if sftp is None:
        client, sftp = (connector or _default_connect)()
        own = True
    try:
        local_root = Path(pair["local"])
        remote_root = pair["remote"]
        resumo = {"added": 0, "updated": 0, "skipped": 0, "bytes": 0,
                  "files": [], "errors": []}
        itens = None
        if client is not None:
            try:
                itens = _walk_remote_fast(client, remote_root)
            except Exception as exc:
                resumo["errors"].append({"path": "<manifest>", "error": str(exc)})
                itens = None
        if itens is None:
            itens = _walk_remote(sftp, remote_root)
        for rpath, remote_path, size, mtime in itens:
            local_file = local_root / rpath
            existe = local_file.exists()
            if not _precisa_baixar(local_file, size, mtime):
                resumo["skipped"] += 1
                continue
            try:
                local_file.parent.mkdir(parents=True, exist_ok=True)
                tmp = local_file.with_name(local_file.name + ".part")
                sftp.get(remote_path, str(tmp))
                os.replace(str(tmp), str(local_file))
                try:
                    os.utime(str(local_file), (mtime, mtime))
                except OSError:
                    pass
                resumo["bytes"] += size
                resumo["files"].append(rpath)
                resumo["updated" if existe else "added"] += 1
            except Exception as exc:
                resumo["errors"].append({"path": rpath, "error": str(exc)})
            if max_files and (resumo["added"] + resumo["updated"]) >= max_files:
                break
        return resumo
    finally:
        if own and client is not None:
            try:
                client.close()
            except Exception:
                pass


def sync_pairs(pairs, sftp=None, connector=None, path=None):
    """Sincroniza varios pares reusando UMA conexao; atualiza last_sync."""
    own = False
    client = None
    if sftp is None:
        client, sftp = (connector or _default_connect)()
        own = True
    try:
        resultados = []
        for pair in pairs:
            r = sync_pair(pair, sftp=sftp, client=client)
            _update_pair(pair["id"], {"last_sync": _now()}, path)
            resultados.append(dict(r, id=pair.get("id")))
        return resultados
    finally:
        if own and client is not None:
            try:
                client.close()
            except Exception:
                pass


def sync_by_id(pair_id, connector=None, path=None):
    pair = _get_pair(pair_id, path)
    if pair is None:
        return None
    return sync_pairs([pair], connector=connector, path=path)[0]


def due_pairs(now=None, path=None):
    """Pares com auto=True cujo intervalo ja passou desde o ultimo sync."""
    now = now if now is not None else _now()
    saida = []
    for p in list_pairs(path):
        if not p.get("auto"):
            continue
        last = p.get("last_sync")
        intervalo = (p.get("interval_min") or DEFAULT_INTERVAL_MIN) * 60
        if last is None or (now - last) >= intervalo:
            saida.append(p)
    return saida


def run_due(now=None, connector=None, path=None):
    """Sincroniza os pares que estao na hora (usado pelo agendador)."""
    pend = due_pairs(now, path)
    if not pend:
        return []
    return sync_pairs(pend, connector=connector, path=path)
