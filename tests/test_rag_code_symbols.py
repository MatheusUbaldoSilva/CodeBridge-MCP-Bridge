import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.chunking.code_symbols import (
    CodeSymbolKind,
    extract_code_symbols,
)


def symbols_by_kind(symbols, kind):
    return [
        symbol
        for symbol in symbols
        if symbol.kind is kind
    ]


class RagCodeSymbolTests(unittest.TestCase):
    def test_python_extracts_module_class_method_function_and_constants(self):
        source = """VERSION = 2

class Service:
    KIND = "worker"

    def run(self):
        return VERSION

def helper():
    return 1
"""
        symbols = extract_code_symbols(
            source,
            path="src/runtime.py",
        )

        self.assertEqual(
            symbols[0].kind,
            CodeSymbolKind.MODULE,
        )
        self.assertEqual(
            symbols[0].name,
            "src.runtime",
        )

        names = {
            (symbol.kind, symbol.qualified_name)
            for symbol in symbols
        }
        self.assertIn(
            (
                CodeSymbolKind.CONSTANT,
                "src.runtime.VERSION",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.CLASS,
                "src.runtime.Service",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.CONSTANT,
                "src.runtime.Service.KIND",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.METHOD,
                "src.runtime.Service.run",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.FUNCTION,
                "src.runtime.helper",
            ),
            names,
        )

    def test_python_does_not_promote_local_uppercase_to_module_constant(self):
        symbols = extract_code_symbols(
            "def f():\n    LOCAL = 1\n    return LOCAL\n",
            path="module.py",
        )
        self.assertFalse(
            any(
                symbol.kind is CodeSymbolKind.CONSTANT
                and symbol.name == "LOCAL"
                for symbol in symbols
            )
        )

    def test_python_init_module_name_uses_package(self):
        symbols = extract_code_symbols(
            "",
            path="rag/chunking/__init__.py",
        )
        self.assertEqual(
            symbols[0].name,
            "rag.chunking",
        )

    def test_powershell_extracts_class_method_function_and_constant(self):
        source = """Set-Variable -Name BuildId -Value 7 -Option Constant

class Worker {
    [int] Run() {
        return 1
    }
}

function Invoke-Test {
    Write-Output ok
}
"""
        symbols = extract_code_symbols(
            source,
            path="runtime.ps1",
        )
        names = {
            (symbol.kind, symbol.qualified_name)
            for symbol in symbols
        }
        self.assertIn(
            (
                CodeSymbolKind.CONSTANT,
                "runtime.BuildId",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.CLASS,
                "runtime.Worker",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.METHOD,
                "runtime.Worker.Run",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.FUNCTION,
                "runtime.Invoke-Test",
            ),
            names,
        )

    def test_javascript_extracts_const_class_method_and_function(self):
        source = """const VERSION = 1;

class Worker {
  run() {
    return VERSION;
  }
}

function helper() {
  return 1;
}

const normalize = value => value + 1;
"""
        symbols = extract_code_symbols(
            source,
            path="app.js",
        )
        kinds = {
            (symbol.kind, symbol.qualified_name)
            for symbol in symbols
        }
        self.assertIn(
            (
                CodeSymbolKind.CONSTANT,
                "app.VERSION",
            ),
            kinds,
        )
        self.assertIn(
            (
                CodeSymbolKind.METHOD,
                "app.Worker.run",
            ),
            kinds,
        )
        self.assertIn(
            (
                CodeSymbolKind.FUNCTION,
                "app.helper",
            ),
            kinds,
        )
        self.assertIn(
            (
                CodeSymbolKind.FUNCTION,
                "app.normalize",
            ),
            kinds,
        )
        self.assertNotIn(
            (
                CodeSymbolKind.CONSTANT,
                "app.normalize",
            ),
            kinds,
        )

    def test_typescript_extracts_namespace(self):
        source = """namespace Bridge {
  export const VERSION = 2;

  export function run() {
    return VERSION;
  }
}
"""
        symbols = extract_code_symbols(
            source,
            path="bridge.ts",
        )
        namespaces = symbols_by_kind(
            symbols,
            CodeSymbolKind.NAMESPACE,
        )
        self.assertEqual(
            [item.qualified_name for item in namespaces],
            ["bridge.Bridge"],
        )

    def test_cpp_extracts_namespace_class_method_function_and_constant(self):
        source = """#define BUILD_ID 7

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
        symbols = extract_code_symbols(
            source,
            path="bridge.cpp",
        )
        names = {
            (symbol.kind, symbol.qualified_name)
            for symbol in symbols
        }
        self.assertIn(
            (
                CodeSymbolKind.CONSTANT,
                "bridge.BUILD_ID",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.NAMESPACE,
                "bridge.bridge",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.CLASS,
                "bridge.bridge.Worker",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.METHOD,
                "bridge.bridge.Worker.run",
            ),
            names,
        )
        self.assertIn(
            (
                CodeSymbolKind.FUNCTION,
                "bridge.bridge.helper",
            ),
            names,
        )

    def test_cpp_out_of_class_method_uses_native_qualifier(self):
        source = """class Worker {
public:
    int run();
};

int Worker::run() {
    return 1;
}
"""
        symbols = extract_code_symbols(
            source,
            path="worker.cpp",
        )
        self.assertTrue(
            any(
                symbol.kind is CodeSymbolKind.METHOD
                and symbol.qualified_name == "worker.Worker.run"
                for symbol in symbols
            )
        )

    def test_strings_and_comments_do_not_create_false_lexical_symbols(self):
        source = """const TEXT = "class Fake { method() {} }";
// function fake() {}
class Real {
  run() {
    return TEXT;
  }
}
"""
        symbols = extract_code_symbols(
            source,
            path="real.js",
        )
        names = {symbol.name for symbol in symbols}
        self.assertNotIn("Fake", names)
        self.assertNotIn("fake", names)
        self.assertIn("Real", names)
        self.assertIn("run", names)

    def test_parent_is_recorded_for_nested_symbols(self):
        symbols = extract_code_symbols(
            "class Service:\n    def run(self):\n        return 1\n",
            path="service.py",
        )
        method = next(
            item
            for item in symbols
            if item.kind is CodeSymbolKind.METHOD
        )
        self.assertEqual(
            method.parent,
            "service.Service",
        )

    def test_empty_registered_source_keeps_module_symbol(self):
        symbols = extract_code_symbols(
            "",
            path="empty.py",
        )
        self.assertEqual(len(symbols), 1)
        self.assertEqual(
            symbols[0].kind,
            CodeSymbolKind.MODULE,
        )
        self.assertEqual(
            (symbols[0].line_start, symbols[0].line_end),
            (1, 1),
        )

    def test_output_is_deterministic(self):
        source = "const VERSION = 1;\nfunction run() { return VERSION; }\n"
        self.assertEqual(
            extract_code_symbols(
                source,
                path="app.js",
            ),
            extract_code_symbols(
                source,
                path="app.js",
            ),
        )


if __name__ == "__main__":
    unittest.main()
