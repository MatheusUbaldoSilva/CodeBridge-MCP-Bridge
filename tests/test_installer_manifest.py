"""Guarda de empacotamento do instalador (installer/CodeBridge.nsi).

Garante que todo modulo runtime do author_mcp alcancavel por import estatico
a partir de mcp_server.py (o entrypoint do MCP) esteja listado como File no
instalador NSIS.

Motivo: a lista de File do author_mcp no .nsi e mantida a mao. Modulos novos
(ex.: *_tools.py) ja ficaram de fora do instalador e a ferramenta sumiu depois
de instalar na maquina. Este teste move essa falha para ANTES do commit, em vez
de ela so aparecer pos-deploy.

So depende da stdlib (ast/re/pathlib/unittest); roda no venv dev sem o pacote
mcp instalado.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTHOR = ROOT / "author_mcp"
NSI = ROOT / "installer" / "CodeBridge.nsi"
ENTRY = AUTHOR / "mcp_server.py"

# captura author_mcp\<nome>.py nas linhas File do instalador
_FILE_RE = re.compile(r"author_mcp\\([A-Za-z0-9_]+\.py)", re.IGNORECASE)


def nsi_listed():
    text = NSI.read_text(encoding="utf-8", errors="replace")
    return {m.group(1) for m in _FILE_RE.finditer(text)}


def _top_imports(py_path):
    """Nomes de modulo de topo importados estaticamente por um arquivo."""
    tree = ast.parse(py_path.read_text(encoding="utf-8", errors="replace"))
    tops = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                tops.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                tops.add(node.module.split(".")[0])
    return tops


def runtime_closure():
    """author_mcp/*.py alcancaveis por import estatico desde mcp_server.py.

    Resolve cada nome de import de topo para author_mcp/<nome>.py; se o arquivo
    irmao existe, e um modulo runtime local e entra no fecho. Imports de
    pacotes (ex.: rag.runtime.*) e de terceiros nao viram author_mcp/<nome>.py
    e por isso sao ignorados -- o pacote rag/ e empacotado por glob a parte.
    """
    needed = {ENTRY.name}
    queue = [ENTRY]
    seen = set()
    while queue:
        cur = queue.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for top in _top_imports(cur):
            sib = AUTHOR / (top + ".py")
            if sib.exists() and sib.name not in needed:
                needed.add(sib.name)
                queue.append(sib)
    return needed


class InstallerManifestTest(unittest.TestCase):
    def test_runtime_modules_estao_no_nsi(self):
        listed = nsi_listed()
        missing = sorted(runtime_closure() - listed)
        self.assertEqual(
            missing,
            [],
            "Modulos runtime do author_mcp importados por mcp_server.py mas "
            "AUSENTES do instalador NSIS (adicione uma linha File para cada em "
            "installer/CodeBridge.nsi): " + ", ".join(missing),
        )

    def test_nsi_nao_lista_arquivo_inexistente(self):
        listed = nsi_listed()
        faltam = sorted(n for n in listed if not (AUTHOR / n).exists())
        self.assertEqual(
            faltam,
            [],
            "Instalador NSIS lista author_mcp/<arquivo> que nao existe mais "
            "(remova a linha File correspondente): " + ", ".join(faltam),
        )


if __name__ == "__main__":
    unittest.main()
