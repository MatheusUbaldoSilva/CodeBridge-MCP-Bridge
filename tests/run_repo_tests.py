"""Run selected unittest modules against this checkout, not installed CodeBridge."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import installer
if Path(installer.__file__).resolve() != ROOT / "installer" / "__init__.py":
    raise RuntimeError("Tests must import the repository installer package")


def main(patterns):
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(
        loader.discover(str(ROOT / "tests"), pattern=pattern)
        for pattern in (patterns or ["test_*.py"])
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
