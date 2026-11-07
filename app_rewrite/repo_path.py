"""Put the repository root on sys.path so the sibling ``rag`` package imports.

main.py runs from app_rewrite/, so Python only sees that folder by default.
Import this module before anything that imports ``rag``.
"""
import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
