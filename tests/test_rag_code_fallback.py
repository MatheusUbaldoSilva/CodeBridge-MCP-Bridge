import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.chunking.code_fallback import (
    FallbackReason,
    ParserMode,
    safe_chunk_code,
)


class RagSafeCodeFallbackTests(unittest.TestCase):
    def test_valid_python_uses_structural_mode(self):
        result = safe_chunk_code(
            "def run():\n    return 1\n",
            path="src/runtime.py",
        )
        self.assertEqual(
            result.parser_mode,
            ParserMode.STRUCTURAL,
        )
        self.assertTrue(result.structural_chunks)
        self.assertTrue(result.symbols)
        self.assertFalse(result.fallback_chunks)
        self.assertIsNone(result.fallback_reason)

    def test_invalid_python_falls_back_instead_of_losing_file(self):
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

        self.assertEqual(
            result.parser_mode,
            ParserMode.FALLBACK,
        )
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.PARSE_ERROR,
        )
        rendered = "\n".join(
            chunk.content
            for chunk in result.fallback_chunks
        )
        self.assertIn("def broken(", rendered)
        self.assertIn("IMPORTANT", rendered)
        self.assertIn("preserve me", rendered)
        self.assertEqual(result.symbols, ())

    def test_malformed_powershell_falls_back(self):
        result = safe_chunk_code(
            "if ($ready) {\nWrite-Output ok\n",
            path="script.ps1",
        )
        self.assertEqual(
            result.parser_mode,
            ParserMode.FALLBACK,
        )
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.PARSE_ERROR,
        )
        self.assertEqual(result.language.value, "POWERSHELL")

    def test_malformed_cpp_falls_back(self):
        result = safe_chunk_code(
            "int main(){\nreturn 0;\n",
            path="main.cpp",
        )
        self.assertEqual(
            result.parser_mode,
            ParserMode.FALLBACK,
        )
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.PARSE_ERROR,
        )
        self.assertEqual(result.language.value, "C_CPP")

    def test_unsupported_bash_uses_textual_fallback(self):
        result = safe_chunk_code(
            "echo one\necho two\n",
            path="script.sh",
        )
        self.assertEqual(
            result.parser_mode,
            ParserMode.FALLBACK,
        )
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.UNSUPPORTED_LANGUAGE,
        )
        self.assertIsNone(result.language)
        self.assertEqual(
            result.fallback_chunks[0].content,
            "echo one\necho two",
        )

    def test_unsupported_cmd_uses_textual_fallback(self):
        result = safe_chunk_code(
            "@echo off\necho ok\n",
            path="setup.cmd",
        )
        self.assertEqual(
            result.parser_mode,
            ParserMode.FALLBACK,
        )
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.UNSUPPORTED_LANGUAGE,
        )

    def test_fallback_prefers_blank_line_logical_blocks(self):
        result = safe_chunk_code(
            "one\ntwo\n\nthree\nfour\n",
            path="script.sh",
        )
        self.assertEqual(
            [item.content for item in result.fallback_chunks],
            [
                "one\ntwo",
                "three\nfour",
            ],
        )

    def test_fallback_has_controlled_line_limit(self):
        source = "\n".join(
            f"line {index}"
            for index in range(1, 8)
        )
        result = safe_chunk_code(
            source,
            path="script.sh",
            fallback_max_lines=3,
        )
        self.assertEqual(
            [
                (item.line_start, item.line_end)
                for item in result.fallback_chunks
            ],
            [
                (1, 3),
                (4, 6),
                (7, 7),
            ],
        )
        self.assertFalse(
            result.fallback_chunks[0].continuation
        )
        self.assertTrue(
            result.fallback_chunks[1].continuation
        )
        self.assertTrue(
            result.fallback_chunks[2].continuation
        )

    def test_nonblank_lines_are_not_silently_lost(self):
        source = "a\nb\n\nc\nd\ne\n"
        result = safe_chunk_code(
            source,
            path="script.sh",
            fallback_max_lines=2,
        )
        recovered = [
            line
            for chunk in result.fallback_chunks
            for line in chunk.content.splitlines()
            if line.strip()
        ]
        original = [
            line
            for line in source.splitlines()
            if line.strip()
        ]
        self.assertEqual(recovered, original)

    def test_parser_error_is_preserved_for_diagnostics(self):
        result = safe_chunk_code(
            "def broken(:\n    pass\n",
            path="broken.py",
        )
        self.assertEqual(
            result.parser_error_type,
            "CodeParseError",
        )
        self.assertIn(
            "PYTHON parse error",
            result.parser_error_message,
        )

    def test_empty_unsupported_file_is_still_explicit_fallback(self):
        result = safe_chunk_code(
            "",
            path="empty.sh",
        )
        self.assertEqual(
            result.parser_mode,
            ParserMode.FALLBACK,
        )
        self.assertEqual(result.fallback_chunks, ())
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.UNSUPPORTED_LANGUAGE,
        )

    def test_unexpected_internal_errors_are_not_swallowed(self):
        with patch(
            "rag.chunking.code_fallback.chunk_code_units",
            side_effect=RuntimeError("internal bug"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "internal bug",
            ):
                safe_chunk_code(
                    "def run():\n    pass\n",
                    path="run.py",
                )

    def test_invalid_fallback_limit_is_rejected_only_when_fallback_is_needed(self):
        with self.assertRaises(ValueError):
            safe_chunk_code(
                "echo ok\n",
                path="script.sh",
                fallback_max_lines=0,
            )

    def test_deterministic_fallback(self):
        source = "one\ntwo\nthree\n"
        self.assertEqual(
            safe_chunk_code(
                source,
                path="script.sh",
                fallback_max_lines=2,
            ),
            safe_chunk_code(
                source,
                path="script.sh",
                fallback_max_lines=2,
            ),
        )


if __name__ == "__main__":
    unittest.main()
