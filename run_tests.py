#!/usr/bin/env python3
"""Runner unico de testes do CodeBridge MCP Bridge.

Motivo: os testes vivem em tests/ e so sao encontrados rodando de dentro dessa
pasta (nao ha __init__/discover a partir da raiz). Alem disso, ~150 dos 668
arquivos sao testes pesados de laboratorio/e2e/live que podem pendurar ou
exigir servicos externos. Sem um ponto unico, cada um roda os testes de um
jeito e regressao passa silenciosa ate instalar na maquina.

Este runner da um comando so:

    python run_tests.py            # suite RAPIDA (exclui os pesados)
    python run_tests.py --full     # TUDO, inclusive lab/e2e/live (lento)
    python run_tests.py --pattern command_log   # so os que casam o filtro
    python run_tests.py --list     # mostra o que seria rodado, sem rodar

Cada modulo roda em seu proprio subprocesso com timeout, entao um teste
pendurado vira falha (TIMEOUT) em vez de travar o runner inteiro. Codigo de
saida != 0 se qualquer modulo falhar/estourar o tempo -- pronto para CI.

So depende da stdlib.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "tests"

# Marcadores de nome de testes PESADOS (laboratorio, e2e, processos reais,
# servicos externos, supervisores/canary). Excluidos da suite rapida; incluidos
# so com --full. Casamento por substring no nome do arquivo, minusculo.
HEAVY_MARKERS = (
    "lab", "e2e", "live", "trial", "readiness", "release", "real",
    "attest", "supervis", "canary", "promotion", "hardcrash", "recovery",
    "rollback", "nsis", "qdrant", "preflight", "postverify", "scheduled",
    "p9b", "gpu", "detached", "interrupt", "failure_injection",
    "process_family", "pid_exit", "offline_lab", "synthetic",
)


def is_heavy(name):
    low = name.lower()
    return any(mark in low for mark in HEAVY_MARKERS)


def select(full, pattern):
    files = sorted(p.name for p in TESTS.glob("test_*.py"))
    out = []
    for name in files:
        if pattern and pattern.lower() not in name.lower():
            continue
        if not full and is_heavy(name):
            continue
        out.append(name)
    return out


def run_module(name, timeout, verbose):
    mod = name[:-3]  # tira .py
    cmd = [sys.executable, "-m", "unittest", "-v" if verbose else "-q", mod]
    try:
        proc = subprocess.run(
            cmd, cwd=str(TESTS), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ""
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    tail = "\n".join(tail[-3:])
    return ("OK" if proc.returncode == 0 else "FALHOU"), tail


def main(argv=None):
    ap = argparse.ArgumentParser(description="Runner unico de testes do CodeBridge")
    ap.add_argument("--full", action="store_true",
                    help="inclui testes pesados (lab/e2e/live); lento")
    ap.add_argument("--pattern", default="",
                    help="roda so os arquivos cujo nome contem este texto")
    ap.add_argument("--timeout", type=int, default=120,
                    help="tempo maximo por modulo, em segundos (padrao 120)")
    ap.add_argument("--list", action="store_true",
                    help="lista os modulos selecionados e sai")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    selected = select(args.full, args.pattern)
    modo = "FULL" if args.full else "RAPIDA"
    print(f"Suite {modo}: {len(selected)} modulo(s) em {TESTS}")
    if args.list:
        for n in selected:
            print("  " + n)
        return 0
    if not selected:
        print("Nenhum teste selecionado.")
        return 1

    inicio = time.time()
    falhas = []
    for i, name in enumerate(selected, 1):
        status, tail = run_module(name, args.timeout, args.verbose)
        marca = "." if status == "OK" else "X"
        print(f"[{i}/{len(selected)}] {marca} {status:7} {name}")
        if status != "OK":
            falhas.append((name, status, tail))

    dur = time.time() - inicio
    print("-" * 60)
    print(f"Total: {len(selected)}  OK: {len(selected) - len(falhas)}  "
          f"Falhas: {len(falhas)}  ({dur:.1f}s)")
    for name, status, tail in falhas:
        print(f"\n### {status}: {name}")
        if tail:
            print(tail)
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
