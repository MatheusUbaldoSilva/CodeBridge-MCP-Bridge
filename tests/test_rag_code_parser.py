import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.chunking.code_parser import (
    CodeLanguage,
    CodeParseError,
    ParserBackend,
    UnsupportedCodeLanguageError,
    detect_code_language,
    parse_code_source,
)


class RagCodeParserTests(unittest.TestCase):
    def test_language_detection_covers_priority_families(self):
        cases = {
            "module.py": CodeLanguage.PYTHON,
            "script.ps1": CodeLanguage.POWERSHELL,
            "app.js": CodeLanguage.JAVASCRIPT,
            "app.ts": CodeLanguage.TYPESCRIPT,
            "main.c": CodeLanguage.C_CPP,
            "main.cc": CodeLanguage.C_CPP,
            "main.cpp": CodeLanguage.C_CPP,
            "main.h": CodeLanguage.C_CPP,
            "main.hpp": CodeLanguage.C_CPP,
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(detect_code_language(path), expected)

    def test_python_uses_stdlib_ast(self):
        result = parse_code_source(
            "class A:\n    def value(self):\n        return 1\n",
            path="src/module.py",
        )
        self.assertEqual(result.language, CodeLanguage.PYTHON)
        self.assertEqual(result.backend, ParserBackend.PYTHON_AST)
        self.assertEqual(result.line_count, 3)

    def test_python_syntax_error_is_structured(self):
        with self.assertRaises(CodeParseError) as captured:
            parse_code_source("def broken(:\n    pass\n", path="broken.py")
        self.assertEqual(captured.exception.language, CodeLanguage.PYTHON)
        self.assertEqual(captured.exception.line, 1)

    def test_powershell_ignores_strings_comments_and_here_strings(self):
        source = """$map = @{ value = @(1, 2) }
# ignored: } ] )
$text = "{ ignored }"
$raw = @'
{ ignored here }
'@
Write-Output ($map.value)
"""
        result = parse_code_source(source, path=r"scripts\runtime.ps1")
        self.assertEqual(result.language, CodeLanguage.POWERSHELL)
        self.assertEqual(result.backend, ParserBackend.POWERSHELL_LEXICAL)
        self.assertEqual(result.path, "scripts/runtime.ps1")
        self.assertGreater(result.delimiter_pairs, 0)

    def test_powershell_unclosed_structure_fails(self):
        with self.assertRaisesRegex(CodeParseError, "unclosed delimiter"):
            parse_code_source("if ($ready) {\nWrite-Output ok\n", path="a.ps1")

    def test_javascript_and_typescript_share_ecmascript_scanner(self):
        javascript = parse_code_source(
            "function x(){ return {value:[1,2]}; }\n"
            "// ignored }\n"
            "const text = `ignored { }`;\n",
            path="app.js",
        )
        typescript = parse_code_source(
            "const x = (value: number) => ({value});\n",
            path="app.ts",
        )
        self.assertEqual(javascript.backend, ParserBackend.ECMASCRIPT_LEXICAL)
        self.assertEqual(typescript.backend, ParserBackend.ECMASCRIPT_LEXICAL)
        self.assertEqual(typescript.language, CodeLanguage.TYPESCRIPT)

    def test_javascript_mismatched_structure_fails(self):
        with self.assertRaises(CodeParseError):
            parse_code_source("function x(){ return [1, 2}; }", path="app.js")

    def test_c_cpp_family_uses_language_aware_lexical_parser(self):
        result = parse_code_source(
            'int main(){ const char* s = "}"; /* { */ return 0; }\n',
            path="src/main.cpp",
        )
        self.assertEqual(result.language, CodeLanguage.C_CPP)
        self.assertEqual(result.backend, ParserBackend.C_CPP_LEXICAL)
        self.assertEqual(result.delimiter_pairs, 2)

    def test_c_cpp_unclosed_structure_fails(self):
        with self.assertRaisesRegex(CodeParseError, "unclosed delimiter"):
            parse_code_source("int main(){\nreturn 0;\n", path="main.cpp")

    def test_bash_and_cmd_remain_explicitly_unregistered(self):
        for path in ("script.sh", "setup.cmd", "setup.bat"):
            with self.subTest(path=path):
                self.assertIsNone(detect_code_language(path))
                with self.assertRaises(UnsupportedCodeLanguageError):
                    parse_code_source("echo ok", path=path)

    def test_empty_source_is_valid_for_registered_languages(self):
        for path in ("empty.py", "empty.ps1", "empty.js", "empty.cpp"):
            with self.subTest(path=path):
                result = parse_code_source("", path=path)
                self.assertEqual(result.line_count, 0)
                self.assertEqual(result.nonempty_line_count, 0)

    def test_parser_result_does_not_anticipate_chunk_or_symbol_contracts(self):
        result = parse_code_source("def x():\n    pass\n", path="x.py")
        self.assertFalse(hasattr(result, "chunks"))
        self.assertFalse(hasattr(result, "symbols"))
        self.assertFalse(hasattr(result, "functions"))

    def test_parser_is_deterministic(self):
        source = "function x(){ return {a:[1]}; }"
        self.assertEqual(
            parse_code_source(source, path="a.js"),
            parse_code_source(source, path="a.js"),
        )

    def test_non_string_source_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_code_source(None, path="a.py")


if __name__ == "__main__":
    unittest.main()
