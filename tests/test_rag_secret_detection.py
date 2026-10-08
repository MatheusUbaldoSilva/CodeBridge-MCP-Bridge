import tempfile
import unittest
from pathlib import Path

from rag.runtime.index_request import RagIndexScope, plan_rag_index
from rag.sources.secret_detection import (
    SensitiveContentKind,
    contains_sensitive_content,
    scan_sensitive_content,
)


class RagSecretDetectionTests(unittest.TestCase):
    def test_private_key_header_is_sensitive_without_retaining_secret(self):
        content = (
            "notes\n"
            "-----BEGIN PRIVATE KEY-----\n"
            "not-real-key-material\n"
            "-----END PRIVATE KEY-----\n"
        )

        scan = scan_sensitive_content(content)

        self.assertTrue(scan.sensitive)
        self.assertEqual(scan.findings[0].kind, SensitiveContentKind.PRIVATE_KEY)
        self.assertEqual(scan.findings[0].line_number, 2)
        payload = scan.to_dict()
        self.assertNotIn("not-real-key-material", repr(payload))
        self.assertEqual(len(scan.findings[0].fingerprint), 12)

    def test_high_confidence_provider_tokens_are_sensitive(self):
        cases = {
            "sk-" + "A" * 28: SensitiveContentKind.OPENAI_KEY,
            "ghp_" + "B" * 40: SensitiveContentKind.GITHUB_TOKEN,
            "AKIA" + "C" * 16: SensitiveContentKind.AWS_ACCESS_KEY,
            "AIza" + "D" * 35: SensitiveContentKind.GOOGLE_API_KEY,
            "xoxb-" + "1" * 12 + "-" + "E" * 24: SensitiveContentKind.SLACK_TOKEN,
        }
        for value, expected in cases.items():
            with self.subTest(expected=expected):
                scan = scan_sensitive_content(f"value={value}\n")
                self.assertTrue(scan.sensitive)
                self.assertEqual(scan.findings[0].kind, expected)
                self.assertNotIn(value, repr(scan.to_dict()))

    def test_secret_assignment_with_real_value_is_sensitive(self):
        content = 'client_secret = "this-is-a-realistic-secret-value"\n'
        scan = scan_sensitive_content(content)
        self.assertTrue(scan.sensitive)
        self.assertEqual(
            scan.findings[0].kind,
            SensitiveContentKind.SECRET_ASSIGNMENT,
        )

    def test_placeholders_and_runtime_references_are_not_secrets(self):
        env_ref = "$" + "{CODEBRIDGE_API_KEY}"
        safe_cases = (
            'api_key = "<REDACTED>"',
            f'api_key = "{env_ref}"',
            'password = "changeme"',
            'token = "your_token"',
            'client_secret = os.getenv("CLIENT_SECRET")',
            'api_key = process.env.API_KEY',
            'password = None',
            'TOKEN = "TOKEN"',
            'CREDENTIAL = "CREDENTIAL"',
            'PRIVATE_KEY = "PRIVATE_KEY"',
        )
        for content in safe_cases:
            with self.subTest(content=content):
                self.assertFalse(contains_sensitive_content(content))

    def test_ordinary_source_hashes_and_ids_are_not_secrets(self):
        content = (
            "sha256 = '3a09a8817b852b5a4faaa6ebb1a5590322746d2b570b578d0b7e3b6e849062aa'\n"
            "request_id = 'req_1234567890abcdef1234567890abcdef'\n"
            "model_id = 'jina-code-embeddings-1.5b'\n"
        )
        self.assertFalse(contains_sensitive_content(content))

    def test_safe_filename_with_secret_content_is_denied_from_index_plan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text(
                "# Safe documentation\n",
                encoding="utf-8",
            )
            (root / "config.py").write_text(
                'api_key = "live-secret-value-1234567890"\n',
                encoding="utf-8",
            )

            plan = plan_rag_index(
                "codebridge",
                root,
                scope=RagIndexScope.BOTH,
            )

            paths = {item.path for item in plan.candidates}
            self.assertIn("README.md", paths)
            self.assertNotIn("config.py", paths)
            self.assertEqual(plan.sensitive_count, 1)
            self.assertGreaterEqual(plan.denied_count, 1)
            self.assertEqual(plan.to_dict()["sensitive_count"], 1)

    def test_placeholder_content_remains_indexable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env_ref = "$" + "{CODEBRIDGE_API_KEY}"
            (root / "config.py").write_text(
                f'api_key = "{env_ref}"\n',
                encoding="utf-8",
            )

            plan = plan_rag_index(
                "codebridge",
                root,
                scope=RagIndexScope.CODE,
            )

            self.assertEqual(
                [item.path for item in plan.candidates],
                ["config.py"],
            )
            self.assertEqual(plan.sensitive_count, 0)

    def test_path_denylist_still_runs_before_content_scanning(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".env").write_text(
                'SAFE_PLACEHOLDER="example"\n',
                encoding="utf-8",
            )

            plan = plan_rag_index("codebridge", root)

            self.assertEqual(plan.candidate_count, 0)
            self.assertEqual(plan.sensitive_count, 0)
            self.assertEqual(plan.denied_count, 1)


if __name__ == "__main__":
    unittest.main()
