import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.chunking.code_parser import (
    CodeParseError,
    UnsupportedCodeLanguageError,
)
from rag.chunking.code_units import (
    CodeUnitKind,
    chunk_code_units,
)


PYTHON_SOURCE = """import os
VALUE = 1

class Service:
    kind = "x"

    def run(self):
        return 1

def helper():
    return 2
"""

POWERSHELL_SOURCE = """$global = 1

class Worker {
    [int] $Value
    [int] Run() {
        return $this.Value
    }
}

function Invoke-Test {
    Write-Output ok
}
"""

JAVASCRIPT_SOURCE = """const VERSION = 1;

class Worker {
  value = 1;
  run() {
    return this.value;
  }
}

function helper() {
  return 2;
}
"""

CPP_SOURCE = """int VALUE = 1;

class Worker {
public:
    int value;
    int run() {
        return value;
    }
};

int helper() {
    return 2;
}
"""


class RagCodeUnitTests(unittest.TestCase):
    def test_python_prefers_structural_units(self):
        chunks = chunk_code_units(
            PYTHON_SOURCE,
            path="src/module.py",
        )

        self.assertEqual(
            [chunk.kind for chunk in chunks],
            [
                CodeUnitKind.LOGICAL_BLOCK,
                CodeUnitKind.CLASS,
                CodeUnitKind.LOGICAL_BLOCK,
                CodeUnitKind.METHOD,
                CodeUnitKind.FUNCTION,
            ],
        )
        self.assertEqual(
            (chunks[1].line_start, chunks[1].line_end),
            (4, 4),
        )
        self.assertEqual(
            (chunks[3].line_start, chunks[3].line_end),
            (7, 8),
        )

    def test_python_class_without_methods_can_stay_whole(self):
        chunks = chunk_code_units(
            "class Config:\n    VALUE = 1\n    NAME = 'x'\n",
            path="config.py",
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].kind, CodeUnitKind.CLASS)
        self.assertEqual(
            (chunks[0].line_start, chunks[0].line_end),
            (1, 3),
        )

    def test_powershell_class_method_and_function(self):
        chunks = chunk_code_units(
            POWERSHELL_SOURCE,
            path="runtime.ps1",
        )
        self.assertEqual(
            [chunk.kind for chunk in chunks],
            [
                CodeUnitKind.LOGICAL_BLOCK,
                CodeUnitKind.CLASS,
                CodeUnitKind.LOGICAL_BLOCK,
                CodeUnitKind.METHOD,
                CodeUnitKind.FUNCTION,
            ],
        )
        self.assertIn(
            "return $this.Value",
            chunks[3].content,
        )

    def test_javascript_class_method_and_function(self):
        chunks = chunk_code_units(
            JAVASCRIPT_SOURCE,
            path="app.js",
        )
        self.assertEqual(
            [chunk.kind for chunk in chunks],
            [
                CodeUnitKind.LOGICAL_BLOCK,
                CodeUnitKind.CLASS,
                CodeUnitKind.LOGICAL_BLOCK,
                CodeUnitKind.METHOD,
                CodeUnitKind.FUNCTION,
            ],
        )

    def test_typescript_expression_arrow_is_a_function_unit(self):
        chunks = chunk_code_units(
            "const VALUE = 1;\n\n"
            "const normalize = (value: number) => value + 1;\n",
            path="app.ts",
        )
        self.assertEqual(chunks[-1].kind, CodeUnitKind.FUNCTION)
        self.assertEqual(
            (chunks[-1].line_start, chunks[-1].line_end),
            (3, 3),
        )

    def test_cpp_class_method_and_function(self):
        chunks = chunk_code_units(
            CPP_SOURCE,
            path="src/main.cpp",
        )
        self.assertEqual(
            [chunk.kind for chunk in chunks],
            [
                CodeUnitKind.LOGICAL_BLOCK,
                CodeUnitKind.CLASS,
                CodeUnitKind.LOGICAL_BLOCK,
                CodeUnitKind.METHOD,
                CodeUnitKind.FUNCTION,
            ],
        )
        self.assertIn("public:", chunks[2].content)

    def test_primary_units_do_not_overlap(self):
        for source, path in (
            (PYTHON_SOURCE, "a.py"),
            (POWERSHELL_SOURCE, "a.ps1"),
            (JAVASCRIPT_SOURCE, "a.js"),
            (CPP_SOURCE, "a.cpp"),
        ):
            with self.subTest(path=path):
                chunks = chunk_code_units(
                    source,
                    path=path,
                )
                for previous, current in zip(
                    chunks,
                    chunks[1:],
                ):
                    self.assertLess(
                        previous.line_end,
                        current.line_start,
                    )

    def test_no_token_count_parameter_exists(self):
        parameters = inspect.signature(
            chunk_code_units
        ).parameters
        self.assertNotIn("max_tokens", parameters)
        self.assertNotIn("token_limit", parameters)
        self.assertNotIn("tokens", parameters)

    def test_symbol_names_are_not_exposed_in_004_b_contract(self):
        chunk = chunk_code_units(
            "def helper():\n    return 1\n",
            path="a.py",
        )[0]
        self.assertFalse(hasattr(chunk, "symbol"))
        self.assertFalse(hasattr(chunk, "name"))

    def test_invalid_source_keeps_parser_error(self):
        with self.assertRaises(CodeParseError):
            chunk_code_units(
                "def broken(:\n    pass\n",
                path="broken.py",
            )

    def test_unsupported_language_is_not_silently_chunked(self):
        with self.assertRaises(UnsupportedCodeLanguageError):
            chunk_code_units(
                "echo ok\n",
                path="script.sh",
            )

    def test_empty_registered_source_returns_no_units(self):
        self.assertEqual(
            chunk_code_units(
                "",
                path="empty.py",
            ),
            (),
        )

    def test_deterministic_output(self):
        self.assertEqual(
            chunk_code_units(
                JAVASCRIPT_SOURCE,
                path="a.js",
            ),
            chunk_code_units(
                JAVASCRIPT_SOURCE,
                path="a.js",
            ),
        )


if __name__ == "__main__":
    unittest.main()
