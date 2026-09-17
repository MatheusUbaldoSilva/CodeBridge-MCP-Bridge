import copy
import subprocess
import threading
import time
from collections import deque

import paramiko
import psutil


class TelemetryService:
    def __init__(self, config_store, credential_store, interval=1.0):
        self.config = config_store
        self.credentials = credential_store
        self.interval = float(interval)
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._threads = []
        self._windows = {"online": False, "error": None}
        self._linux = {"online": False, "error": None}
        self._history = {
            "windows_cpu": deque(maxlen=60),
            "windows_ram": deque(maxlen=60),
            "linux_cpu": deque(maxlen=60),
            "linux_ram": deque(maxlen=60),
        }
        self._linux_client = None
    def start(self):
        if self._threads:
            return False
        self._stop.clear()
        for name, target in (("WindowsTelemetry", self._windows_loop),
                             ("LinuxTelemetry", self._linux_loop)):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._threads.append(thread)
        return True

    def stop(self):
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=2.0)
        self._threads.clear()
        self._close_linux_client()

    def set_interval(self, seconds):
        value = float(seconds)
        if value not in (1.0, 2.0, 5.0):
            raise ValueError("intervalo deve ser 1, 2 ou 5 segundos")
        self.interval = value

    def snapshot(self, kind):
        with self._lock:
            data = self._windows if kind == "windows" else self._linux
            result = copy.deepcopy(data)
            prefix = "windows" if kind == "windows" else "linux"
            result["cpu_history"] = list(self._history[prefix + "_cpu"])
            result["ram_history"] = list(self._history[prefix + "_ram"])
            return result
    @staticmethod
    def _rate(current, previous, elapsed):
        if previous is None or elapsed <= 0:
            return 0.0
        return max(0.0, (current - previous) / elapsed)

    @staticmethod
    def _gpu_snapshot():
        command = [
            "nvidia-smi",
            "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None
            parts = [part.strip() for part in result.stdout.splitlines()[0].split(",")]
            return {
                "name": parts[0], "percent": float(parts[1]),
                "used_mb": float(parts[2]), "total_mb": float(parts[3]),
                "temp_c": float(parts[4]),
            }
        except Exception:
            return None
    def _windows_loop(self):
        psutil.cpu_percent(interval=None)
        prev_disk = psutil.disk_io_counters()
        prev_net = psutil.net_io_counters()
        prev_time = time.monotonic()
        gpu = None
        gpu_at = 0.0
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                cpu = psutil.cpu_percent(interval=None)
                freq = psutil.cpu_freq()
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage("C:\\")
                disk_io = psutil.disk_io_counters()
                net = psutil.net_io_counters()
                now = time.monotonic()
                elapsed = max(0.001, now - prev_time)
                if now - gpu_at >= 2.0:
                    gpu = self._gpu_snapshot()
                    gpu_at = now
                payload = {
                    "online": True, "error": None, "timestamp": time.time(),
                    "cpu_percent": cpu,
                    "cpu_ghz": (freq.current / 1000.0) if freq else None,
                    "cpu_cores": psutil.cpu_count(logical=True),
                    "ram_percent": mem.percent,
                    "ram_used": mem.used, "ram_total": mem.total,
                    "disk_percent": disk.percent,
                    "disk_used": disk.used, "disk_total": disk.total,
                    "disk_read_bps": self._rate(disk_io.read_bytes, prev_disk.read_bytes, elapsed),
                    "disk_write_bps": self._rate(disk_io.write_bytes, prev_disk.write_bytes, elapsed),
                    "net_down_bps": self._rate(net.bytes_recv, prev_net.bytes_recv, elapsed),
                    "net_up_bps": self._rate(net.bytes_sent, prev_net.bytes_sent, elapsed),
                    "uptime": max(0.0, time.time() - psutil.boot_time()),
                    "gpu": gpu,
                }
                with self._lock:
                    self._windows = payload
                    self._history["windows_cpu"].append(cpu)
                    self._history["windows_ram"].append(mem.percent)
                prev_disk, prev_net, prev_time = disk_io, net, now
            except Exception as exc:
                with self._lock:
                    self._windows = {"online": False, "error": str(exc), "timestamp": time.time()}
            delay = max(0.05, self.interval - (time.monotonic() - started))
            self._stop.wait(delay)
    def _close_linux_client(self):
        with self._lock:
            client = self._linux_client
            self._linux_client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def _ensure_linux_client(self):
        with self._lock:
            client = self._linux_client
        transport = client.get_transport() if client is not None else None
        if transport is not None and transport.is_active():
            return client
        self._close_linux_client()
        config = self.config.load_ssh()
        creds = self.credentials.load()
        if not config or not creds:
            raise RuntimeError("SSH nao configurado para telemetria")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            config["host"], port=int(config["port"]),
            username=creds["username"], password=creds["password"],
            timeout=5, banner_timeout=5, auth_timeout=5,
        )
        with self._lock:
            self._linux_client = client
        return client
    @staticmethod
    def _linux_command():
        return (
            "LC_ALL=C sh -c '"
            "head -n1 /proc/stat; "
            "echo __LOAD__; cat /proc/loadavg; "
            "echo __UP__; cut -d\" \" -f1 /proc/uptime; "
            "echo __MEM__; cat /proc/meminfo; "
            "echo __DISK__; df -Pk / | tail -n1; "
            "echo __NET__; cat /proc/net/dev; "
            "echo __PROC__; ps -e --no-headers 2>/dev/null | wc -l; "
            "echo __TOPCPU__; ps -eo comm=,pcpu= --sort=-pcpu 2>/dev/null | head -n3; "
            "echo __TOPMEM__; ps -eo comm=,rss= --sort=-rss 2>/dev/null | head -n3'"
        )

    @staticmethod
    def _section(lines, marker):
        try:
            start = lines.index(marker) + 1
        except ValueError:
            return []
        end = len(lines)
        for index in range(start, len(lines)):
            if lines[index].startswith("__") and lines[index].endswith("__"):
                end = index
                break
        return lines[start:end]
    @staticmethod
    def _parse_top(lines, memory=False):
        result = []
        for line in lines[:3]:
            parts = line.split()
            if len(parts) < 2:
                continue
            name = " ".join(parts[:-1])
            try:
                value = float(parts[-1])
            except ValueError:
                continue
            if memory:
                value *= 1024.0
            result.append({"name": name, "value": value})
        return result

    def _collect_linux(self, prev_cpu, prev_net, prev_time):
        client = self._ensure_linux_client()
        _, stdout, stderr = client.exec_command(self._linux_command(), timeout=5)
        text = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace").strip()
        if not text.strip():
            raise RuntimeError(error or "telemetria SSH sem resposta")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cpu_line = lines[0].split()
        cpu_values = [int(value) for value in cpu_line[1:]]
        idle = cpu_values[3] + (cpu_values[4] if len(cpu_values) > 4 else 0)
        total = sum(cpu_values)
        if prev_cpu is None:
            cpu_percent = 0.0
        else:
            prev_total, prev_idle = prev_cpu
            total_delta = max(1, total - prev_total)
            idle_delta = max(0, idle - prev_idle)
            cpu_percent = max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))
        load = self._section(lines, "__LOAD__")
        load_values = [float(v) for v in load[0].split()[:3]] if load else [0.0, 0.0, 0.0]
        up = self._section(lines, "__UP__")
        uptime = float(up[0]) if up else 0.0
        mem = {}
        for line in self._section(lines, "__MEM__"):
            if ":" in line:
                key, value = line.split(":", 1)
                parts = value.split()
                if parts and parts[0].isdigit():
                    mem[key] = float(parts[0]) * 1024.0
        mem_total = mem.get("MemTotal", 0.0)
        mem_available = mem.get("MemAvailable", 0.0)
        swap_total = mem.get("SwapTotal", 0.0)
        swap_free = mem.get("SwapFree", 0.0)
        mem_used = max(0.0, mem_total - mem_available)
        mem_percent = (mem_used / mem_total * 100.0) if mem_total else 0.0
        disk = self._section(lines, "__DISK__")
        disk_parts = disk[0].split() if disk else []
        disk_total = float(disk_parts[1]) * 1024.0 if len(disk_parts) >= 5 else 0.0
        disk_used = float(disk_parts[2]) * 1024.0 if len(disk_parts) >= 5 else 0.0
        disk_percent = float(disk_parts[4].rstrip("%")) if len(disk_parts) >= 5 else 0.0
        rx = tx = 0.0
        for line in self._section(lines, "__NET__"):
            if ":" not in line:
                continue
            _, values = line.split(":", 1)
            fields = values.split()
            if len(fields) >= 9:
                try:
                    rx += float(fields[0])
                    tx += float(fields[8])
                except ValueError:
                    pass
        now = time.monotonic()
        elapsed = max(0.001, now - prev_time) if prev_time is not None else 1.0
        down_bps = self._rate(rx, prev_net[0], elapsed) if prev_net else 0.0
        up_bps = self._rate(tx, prev_net[1], elapsed) if prev_net else 0.0
        proc = self._section(lines, "__PROC__")
        process_count = int(proc[0]) if proc and proc[0].isdigit() else 0
        payload = {
            "online": True, "error": None, "timestamp": time.time(),
            "cpu_percent": cpu_percent,
            "load1": load_values[0], "load5": load_values[1], "load15": load_values[2],
            "ram_percent": mem_percent, "ram_used": mem_used, "ram_total": mem_total,
            "swap_used": max(0.0, swap_total - swap_free), "swap_total": swap_total,
            "disk_percent": disk_percent, "disk_used": disk_used, "disk_total": disk_total,
            "net_down_bps": down_bps, "net_up_bps": up_bps,
            "process_count": process_count, "uptime": uptime,
            "top_cpu": self._parse_top(self._section(lines, "__TOPCPU__")),
            "top_mem": self._parse_top(self._section(lines, "__TOPMEM__"), memory=True),
        }
        return payload, (total, idle), (rx, tx), now
    def _linux_loop(self):
        prev_cpu = None
        prev_net = None
        prev_time = None
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                payload, prev_cpu, prev_net, prev_time = self._collect_linux(
                    prev_cpu, prev_net, prev_time
                )
                with self._lock:
                    self._linux = payload
                    self._history["linux_cpu"].append(payload["cpu_percent"])
                    self._history["linux_ram"].append(payload["ram_percent"])
            except Exception as exc:
                self._close_linux_client()
                with self._lock:
                    self._linux = {
                        "online": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "timestamp": time.time(),
                    }
                prev_cpu = prev_net = prev_time = None
            delay = max(0.05, self.interval - (time.monotonic() - started))
            self._stop.wait(delay)
