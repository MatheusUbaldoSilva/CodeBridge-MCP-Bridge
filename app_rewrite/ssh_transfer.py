"""Canal de arquivos Windows <-> Linux por SFTP.

Usa a mesma conexao SSH confiavel do terminal (known_hosts + RejectPolicy):
servidor com chave desconhecida ou trocada e recusado. Arquivos e pastas
nos dois sentidos, com progresso, cancelamento e sem sobrescrever por
padrao. Cada arquivo e gravado primeiro como <nome>.cbpart e so ganha o
nome final quando chega inteiro.
"""
import os
import posixpath
import stat
import threading
import time
import uuid
from pathlib import Path

import paramiko

PART = ".cbpart"
CHUNK = 256 * 1024
UPLOAD = "UPLOAD"
DOWNLOAD = "DOWNLOAD"
_BAD_WINDOWS_CHARS = set('<>:"/\\|?*')
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {
    f"LPT{i}" for i in range(1, 10)}


class TransferCancelled(Exception):
    pass


class TransferConflict(FileExistsError):
    def __init__(self, paths):
        self.paths = list(paths)
        shown = ", ".join(self.paths[:5])
        more = f" (+{len(self.paths) - 5})" if len(self.paths) > 5 else ""
        super().__init__("Ja existe no destino: " + shown + more)


def connect_sftp(host, port, username, password, timeout=10):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(
        hostname=host, port=int(port), username=username, password=password,
        look_for_keys=False, allow_agent=False, timeout=timeout,
        banner_timeout=timeout, auth_timeout=timeout,
    )
    return client, client.open_sftp()


def windows_name_problem(name):
    if not name or name in (".", ".."):
        return "nome vazio"
    if any(ch in _BAD_WINDOWS_CHARS or ord(ch) < 32 for ch in name):
        return "caractere proibido no Windows"
    if name[-1] in " .":
        return "termina com espaco ou ponto"
    if name.split(".")[0].upper() in _RESERVED:
        return "nome reservado no Windows"
    return None


def list_local(path):
    root = Path(path)
    if not root.is_dir():
        raise NotADirectoryError(f"Pasta nao encontrada: {root}")
    items = []
    with os.scandir(root) as entries:
        for entry in entries:
            try:
                is_link = entry.is_symlink()
                is_dir = entry.is_dir(follow_symlinks=False)
                info = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            items.append({
                "name": entry.name, "path": str(root / entry.name),
                "is_dir": is_dir, "is_link": is_link,
                "size": 0 if is_dir else int(info.st_size),
                "mtime": int(info.st_mtime),
            })
    return _sorted(items)


def _sorted(items):
    return sorted(items, key=lambda i: (not i["is_dir"], i["name"].lower()))


class SshFileChannel:
    """Uma conexao SFTP reaproveitada; reconecta se cair."""

    def __init__(self, opener):
        self._opener = opener
        self._client = None
        self._sftp = None
        self._lock = threading.RLock()

    def sftp(self):
        with self._lock:
            transport = self._client.get_transport() if self._client else None
            if self._sftp is None or transport is None or not transport.is_active():
                self.close()
                self._client, self._sftp = self._opener()
            return self._sftp

    def close(self):
        with self._lock:
            for item in (self._sftp, self._client):
                try:
                    if item is not None:
                        item.close()
                except Exception:
                    pass
            self._client = None
            self._sftp = None

    def home(self):
        return self.sftp().normalize(".")

    def list_remote(self, path):
        sftp = self.sftp()
        path = sftp.normalize(path or ".")
        items = []
        for attr in sftp.listdir_attr(path):
            mode = attr.st_mode or 0
            is_link = stat.S_ISLNK(mode)
            is_dir = stat.S_ISDIR(mode)
            if is_link:
                try:
                    is_dir = stat.S_ISDIR(sftp.stat(posixpath.join(path, attr.filename)).st_mode)
                except (IOError, OSError):
                    is_dir = False
            items.append({
                "name": attr.filename, "path": posixpath.join(path, attr.filename),
                "is_dir": is_dir, "is_link": is_link,
                "size": 0 if is_dir else int(attr.st_size or 0),
                "mtime": int(attr.st_mtime or 0),
            })
        return path, _sorted(items)

    def _remote_exists(self, path):
        try:
            self.sftp().stat(path)
            return True
        except (IOError, OSError):
            return False

    # ---------- planejamento ----------
    def plan_upload(self, sources, remote_dir):
        sftp = self.sftp()
        remote_dir = sftp.normalize(remote_dir)
        if not stat.S_ISDIR(sftp.stat(remote_dir).st_mode):
            raise NotADirectoryError(f"Destino no Linux nao e pasta: {remote_dir}")
        dirs, files, skipped, conflicts = [], [], [], []
        for raw in sources:
            src = Path(raw)
            if src.is_symlink():
                skipped.append((str(src), "atalho/link ignorado"))
                continue
            if not src.exists():
                raise FileNotFoundError(f"Nao encontrado no Windows: {src}")
            top = posixpath.join(remote_dir, src.name)
            top_exists = self._remote_exists(top)
            if src.is_file():
                files.append((str(src), top, src.stat().st_size))
                if top_exists:
                    conflicts.append(top)
                continue
            dirs.append(top)
            for base, subdirs, names in os.walk(src, followlinks=False):
                rel = Path(base).relative_to(src).as_posix()
                remote_base = top if rel == "." else posixpath.join(top, rel)
                for d in list(subdirs):
                    full = Path(base) / d
                    if full.is_symlink():
                        subdirs.remove(d)
                        skipped.append((str(full), "atalho/link ignorado"))
                        continue
                    dirs.append(posixpath.join(remote_base, d))
                for n in names:
                    full = Path(base) / n
                    if full.is_symlink():
                        skipped.append((str(full), "atalho/link ignorado"))
                        continue
                    dst = posixpath.join(remote_base, n)
                    files.append((str(full), dst, full.stat().st_size))
                    if top_exists and self._remote_exists(dst):
                        conflicts.append(dst)
        return {"dirs": dirs, "files": files, "skipped": skipped, "conflicts": conflicts}

    def plan_download(self, sources, local_dir):
        sftp = self.sftp()
        local_dir = Path(local_dir)
        if not local_dir.is_dir():
            raise NotADirectoryError(f"Destino no Windows nao e pasta: {local_dir}")
        dirs, files, skipped, conflicts = [], [], [], []

        def walk(remote, local, top_exists):
            for attr in sftp.listdir_attr(remote):
                child = posixpath.join(remote, attr.filename)
                mode = attr.st_mode or 0
                if stat.S_ISLNK(mode):
                    skipped.append((child, "atalho/link ignorado"))
                    continue
                problem = windows_name_problem(attr.filename)
                if problem:
                    skipped.append((child, problem))
                    continue
                target = local / attr.filename
                if stat.S_ISDIR(mode):
                    dirs.append(str(target))
                    walk(child, target, top_exists and target.exists())
                elif stat.S_ISREG(mode):
                    files.append((child, str(target), int(attr.st_size or 0)))
                    if top_exists and target.exists():
                        conflicts.append(str(target))
                else:
                    skipped.append((child, "tipo especial ignorado"))

        for raw in sources:
            remote = sftp.normalize(raw)
            name = posixpath.basename(remote.rstrip("/"))
            problem = windows_name_problem(name)
            if problem:
                raise ValueError(f"{remote}: {problem}")
            info = sftp.stat(remote)
            target = local_dir / name
            if stat.S_ISDIR(info.st_mode):
                dirs.append(str(target))
                walk(remote, target, target.exists())
            else:
                files.append((remote, str(target), int(info.st_size or 0)))
                if target.exists():
                    conflicts.append(str(target))
        return {"dirs": dirs, "files": files, "skipped": skipped, "conflicts": conflicts}

    # ---------- execucao ----------
    def transfer(self, direction, sources, destination, overwrite=False,
                 progress=None, cancelled=None):
        direction = str(direction).upper()
        if direction not in (UPLOAD, DOWNLOAD):
            raise ValueError("direcao deve ser UPLOAD ou DOWNLOAD")
        sources = [str(s) for s in (sources or []) if str(s).strip()]
        if not sources:
            raise ValueError("nada selecionado para transferir")
        plan = (self.plan_upload(sources, destination) if direction == UPLOAD
                else self.plan_download(sources, destination))
        if plan["conflicts"] and not overwrite:
            raise TransferConflict(plan["conflicts"])
        total = sum(size for _, _, size in plan["files"])
        state = {"done_bytes": 0, "total_bytes": total, "done_files": 0,
                 "total_files": len(plan["files"]), "file": None}

        def tick(file_name, delta):
            state["done_bytes"] += delta
            state["file"] = file_name
            if progress:
                progress(dict(state))
            if cancelled and cancelled():
                raise TransferCancelled()

        for d in plan["dirs"]:
            self._mkdir(direction, d)
        for src, dst, _size in plan["files"]:
            if cancelled and cancelled():
                raise TransferCancelled()
            if direction == UPLOAD:
                self._put(src, dst, tick)
            else:
                self._get(src, dst, tick)
            state["done_files"] += 1
            tick(dst, 0)
        return {"direction": direction, "files": state["done_files"],
                "bytes": state["done_bytes"], "dirs": len(plan["dirs"]),
                "skipped": [{"path": p, "reason": r} for p, r in plan["skipped"]],
                "overwritten": len(plan["conflicts"]) if overwrite else 0}

    def _mkdir(self, direction, path):
        if direction == DOWNLOAD:
            Path(path).mkdir(parents=True, exist_ok=True)
            return
        sftp = self.sftp()
        try:
            if stat.S_ISDIR(sftp.stat(path).st_mode):
                return
            raise FileExistsError(f"Existe um arquivo com o nome da pasta: {path}")
        except (IOError, OSError) as exc:
            if isinstance(exc, FileExistsError):
                raise
            sftp.mkdir(path)

    def _put(self, src, dst, tick):
        sftp = self.sftp()
        temp = dst + PART
        try:
            with open(src, "rb") as local, sftp.open(temp, "wb") as remote:
                remote.set_pipelined(True)
                while True:
                    chunk = local.read(CHUNK)
                    if not chunk:
                        break
                    remote.write(chunk)
                    tick(dst, len(chunk))
            try:
                sftp.posix_rename(temp, dst)
            except (IOError, OSError):
                if self._remote_exists(dst):
                    sftp.remove(dst)
                sftp.rename(temp, dst)
            mtime = int(os.path.getmtime(src))
            sftp.utime(dst, (mtime, mtime))
        except BaseException:
            try:
                sftp.remove(temp)
            except Exception:
                pass
            raise

    def _get(self, src, dst, tick):
        sftp = self.sftp()
        target = Path(dst)
        temp = target.with_name(target.name + PART)
        try:
            info = sftp.stat(src)
            with sftp.open(src, "rb") as remote, open(temp, "wb") as local:
                remote.prefetch(int(info.st_size or 0))
                while True:
                    chunk = remote.read(CHUNK)
                    if not chunk:
                        break
                    local.write(chunk)
                    tick(dst, len(chunk))
            os.replace(temp, target)
            if info.st_mtime:
                os.utime(target, (int(info.st_mtime), int(info.st_mtime)))
        except BaseException:
            try:
                temp.unlink()
            except OSError:
                pass
            raise


class TransferRegistry:
    """Transferencias em segundo plano, usadas pela tela e pela IA."""

    KEEP = 30

    def __init__(self, opener, channel_factory=SshFileChannel):
        self._opener = opener
        self._factory = channel_factory
        self._lock = threading.Lock()
        self._items = {}
        self._order = []

    def start(self, direction, sources, destination, overwrite=False, origin="TELA"):
        transfer_id = uuid.uuid4().hex[:12]
        record = {
            "id": transfer_id, "origin": str(origin or "TELA").upper(),
            "direction": str(direction).upper(), "sources": list(sources or []),
            "destination": str(destination), "overwrite": bool(overwrite),
            "state": "RUNNING", "progress": None, "result": None, "error": None,
            "conflicts": [], "started_at": time.time(), "finished_at": None,
            "_cancel": False,
        }
        with self._lock:
            self._items[transfer_id] = record
            self._order.append(transfer_id)
            while len(self._order) > self.KEEP:
                old = self._order.pop(0)
                if self._items.get(old, {}).get("state") == "RUNNING":
                    self._order.insert(0, old)
                    break
                self._items.pop(old, None)
        threading.Thread(target=self._run, args=(transfer_id,),
                         name="CodeBridgeSshTransfer", daemon=True).start()
        return self.status(transfer_id)

    def _run(self, transfer_id):
        record = self._items[transfer_id]
        channel = self._factory(self._opener)

        def progress(state):
            record["progress"] = state

        try:
            record["result"] = channel.transfer(
                record["direction"], record["sources"], record["destination"],
                overwrite=record["overwrite"], progress=progress,
                cancelled=lambda: record["_cancel"],
            )
            record["state"] = "DONE"
        except TransferCancelled:
            record["state"] = "CANCELLED"
        except TransferConflict as exc:
            record["state"] = "CONFLICT"
            record["conflicts"] = exc.paths
            record["error"] = str(exc)
        except Exception as exc:
            record["state"] = "FAILED"
            record["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            record["finished_at"] = time.time()
            channel.close()

    def status(self, transfer_id):
        with self._lock:
            record = self._items.get(str(transfer_id))
            if record is None:
                raise KeyError(transfer_id)
            return {k: v for k, v in record.items() if not k.startswith("_")}

    def cancel(self, transfer_id):
        with self._lock:
            record = self._items.get(str(transfer_id))
            if record is None:
                raise KeyError(transfer_id)
            if record["state"] == "RUNNING":
                record["_cancel"] = True
                return True
            return False

    def recent(self, limit=10):
        with self._lock:
            ids = list(reversed(self._order))[: int(limit)]
        return [self.status(i) for i in ids]