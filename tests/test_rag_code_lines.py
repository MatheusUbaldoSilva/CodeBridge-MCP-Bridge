import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.chunking.code_fallback import (
    ParserMode,
    safe_chunk_code,
)
from rag.chunking.code_lines import (
    CodeLineAccuracyError,
    source_line_slice,
    validate_code_line_accuracy,
)
from rag.chunking.code_symbols import CodeSymbolKind


PYTHON_SOURCE = """VERSION = 1

class Worker:
    KIND = "x"

    def run(self):
        return VERSION

def helper():
    return 1
"""

POWERSHELL_SOURCE = """Set-Variable -Name BuildId -Value 7 -Option Constant

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

CPP_SOURCE = """#define BUILD_ID 7

namespace bridge {
constexpr int VERSION = 2;

class Worker {
public:
    int run() {
        return VERSION;
    }
};

int helper() {
    return VERSION;
}
}
"""


def range_map(result):
    return {
        (symbol.kind, symbol.qualified_name): (
            symbol.line_start,
            symbol.line_end,
        )
        for symbol in result.symbols
    }


class RagCodeLineAccuracyTests(unittest.TestCase):
    def test_python_chunks_are_exact_source_slices(self):
        result = safe_chunk_code(
            PYTHON_SOURCE,
            path="src/runtime.py",
        )
        report = validate_code_line_accuracy(
            PYTHON_SOURCE,
            result,
        )

        self.assertEqual(
            result.parser_mode,
            ParserMode.STRUCTURAL,
        )
        self.assertEqual(
            [
                (chunk.line_start, chunk.line_end)
                for chunk in result.structural_chunks
            ],
            [
                (1, 1),
                (3, 3),
                (4, 4),
                (6, 7),
                (9, 10),
            ],
        )
        self.assertEqual(report.source_line_count, 10)

    def test_python_symbol_ranges_are_frozen(self):
        result = safe_chunk_code(
            PYTHON_SOURCE,
            path="src/runtime.py",
        )
        validate_code_line_accuracy(
            PYTHON_SOURCE,
            result,
        )
        ranges = range_map(result)

        self.assertEqual(
            ranges[(CodeSymbolKind.MODULE, "src.runtime")],
            (1, 10),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.CONSTANT, "src.runtime.VERSION")],
            (1, 1),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.CLASS, "src.runtime.Worker")],
            (3, 7),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.CONSTANT, "src.runtime.Worker.KIND")],
            (4, 4),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.METHOD, "src.runtime.Worker.run")],
            (6, 7),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.FUNCTION, "src.runtime.helper")],
            (9, 10),
        )

    def test_powershell_chunks_and_symbols_have_exact_ranges(self):
        result = safe_chunk_code(
            POWERSHELL_SOURCE,
            path="runtime.ps1",
        )
        validate_code_line_accuracy(
            POWERSHELL_SOURCE,
            result,
        )

        self.assertEqual(
            [
                (chunk.line_start, chunk.line_end)
                for chunk in result.structural_chunks
            ],
            [
                (1, 1),
                (3, 3),
                (4, 4),
                (5, 7),
                (10, 12),
            ],
        )

        ranges = range_map(result)
        self.assertEqual(
            ranges[(CodeSymbolKind.MODULE, "runtime")],
            (1, 12),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.CONSTANT, "runtime.BuildId")],
            (1, 1),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.CLASS, "runtime.Worker")],
            (3, 8),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.METHOD, "runtime.Worker.Run")],
            (5, 7),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.FUNCTION, "runtime.Invoke-Test")],
            (10, 12),
        )

    def test_cpp_chunks_and_symbols_have_exact_ranges(self):
        result = safe_chunk_code(
            CPP_SOURCE,
            path="bridge.cpp",
        )
        validate_code_line_accuracy(
            CPP_SOURCE,
            result,
        )

        self.assertEqual(
            [
                (chunk.line_start, chunk.line_end)
                for chunk in result.structural_chunks
            ],
            [
                (1, 4),
                (6, 6),
                (7, 7),
                (8, 10),
                (13, 15),
            ],
        )

        ranges = range_map(result)
        self.assertEqual(
            ranges[(CodeSymbolKind.MODULE, "bridge")],
            (1, 16),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.CONSTANT, "bridge.BUILD_ID")],
            (1, 1),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.NAMESPACE, "bridge.bridge")],
            (3, 16),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.CONSTANT, "bridge.bridge.VERSION")],
            (4, 4),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.CLASS, "bridge.bridge.Worker")],
            (6, 11),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.METHOD, "bridge.bridge.Worker.run")],
            (8, 10),
        )
        self.assertEqual(
            ranges[(CodeSymbolKind.FUNCTION, "bridge.bridge.helper")],
            (13, 15),
        )

    def test_fallback_chunks_are_exact_source_slices(self):
        source = (
            "def broken(:\n"
            "    return 1\n"
            "\n"
            "IMPORTANT = 'preserve me'\n"
        )
        result = safe_chunk_code(
            source,
            path="broken.py",
        )
        report = validate_code_line_accuracy(
            source,
            result,
        )

        self.assertEqual(
            result.parser_mode,
            ParserMode.FALLBACK,
        )
        self.assertEqual(
            [
                (chunk.line_start, chunk.line_end)
                for chunk in result.fallback_chunks
            ],
            [
                (1, 2),
                (4, 4),
            ],
        )
        self.assertEqual(report.symbol_count, 0)

    def test_line_slice_is_one_based_and_inclusive(self):
        self.assertEqual(
            source_line_slice(
                "one\ntwo\nthree\n",
                line_start=2,
                line_end=3,
            ),
            "two\nthree",
        )

    def test_content_tampering_is_detected(self):
        result = safe_chunk_code(
            PYTHON_SOURCE,
            path="src/runtime.py",
        )
        first = replace(
            result.structural_chunks[0],
            content="tampered",
        )
        tampered = replace(
            result,
            structural_chunks=(
                first,
                *result.structural_chunks[1:],
            ),
        )

        with self.assertRaisesRegex(
            CodeLineAccuracyError,
            "content does not match",
        ):
            validate_code_line_accuracy(
                PYTHON_SOURCE,
                tampered,
            )

    def test_out_of_range_chunk_is_detected(self):
        result = safe_chunk_code(
            "def run():\n    return 1\n",
            path="run.py",
        )
        first = replace(
            result.structural_chunks[0],
            line_end=99,
        )
        tampered = replace(
            result,
            structural_chunks=(first,),
        )

        with self.assertRaisesRegex(
            CodeLineAccuracyError,
            "exceeds source line count",
        ):
            validate_code_line_accuracy(
                "def run():\n    return 1\n",
                tampered,
            )

    def test_symbol_range_tampering_is_detected(self):
        result = safe_chunk_code(
            PYTHON_SOURCE,
            path="src/runtime.py",
        )
        target = next(
            symbol
            for symbol in result.symbols
            if symbol.kind is CodeSymbolKind.METHOD
        )
        changed = replace(
            target,
            line_start=1,
            line_end=1,
        )
        symbols = tuple(
            changed if symbol is target else symbol
            for symbol in result.symbols
        )
        tampered = replace(
            result,
            symbols=symbols,
        )

        with self.assertRaisesRegex(
            CodeLineAccuracyError,
            "not anchored",
        ):
            validate_code_line_accuracy(
                PYTHON_SOURCE,
                tampered,
            )

    def test_empty_python_has_module_range_1_1_and_no_chunks(self):
        result = safe_chunk_code(
            "",
            path="empty.py",
        )
        report = validate_code_line_accuracy(
            "",
            result,
        )
        self.assertEqual(report.source_line_count, 0)
        self.assertEqual(report.chunk_count, 0)
        self.assertEqual(report.symbol_count, 1)
        self.assertEqual(
            (
                result.symbols[0].line_start,
                result.symbols[0].line_end,
            ),
            (1, 1),
        )

    def test_validation_is_deterministic(self):
        first = safe_chunk_code(
            CPP_SOURCE,
            path="bridge.cpp",
        )
        second = safe_chunk_code(
            CPP_SOURCE,
            path="bridge.cpp",
        )
        self.assertEqual(
            validate_code_line_accuracy(
                CPP_SOURCE,
                first,
            ),
            validate_code_line_accuracy(
                CPP_SOURCE,
                second,
            ),
        )


if __name__ == "__main__":
    unittest.main()
