import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import read_only_batch as rob


class ReadOnlyBatchTests(unittest.TestCase):
    def test_rejects_unknown_kind_before_execution(self):
        with patch.object(
            rob,
            "_execute_item",
        ) as execute:
            with self.assertRaises(
                rob.ReadOnlyBatchValidationError
            ):
                rob.execute_read_only_batch([
                    {"kind": "DELETE_FILE", "path": "x"}
                ])
        execute.assert_not_called()

    def test_rejects_command_field_before_execution(self):
        with patch.object(
            rob,
            "_execute_item",
        ) as execute:
            with self.assertRaises(
                rob.ReadOnlyBatchValidationError
            ):
                rob.execute_read_only_batch([
                    {
                        "kind": "FILE_STAT",
                        "path": __file__,
                        "command": "whoami",
                    }
                ])
        execute.assert_not_called()

    def test_rejects_more_than_32_items(self):
        operations = [
            {"kind": "VERSION"}
            for _ in range(33)
        ]
        with self.assertRaises(
            rob.ReadOnlyBatchValidationError
        ):
            rob.execute_read_only_batch(operations)

    def test_version_and_missing_file_are_item_isolated(self):
        result = rob.execute_read_only_batch([
            {"id": "v", "kind": "VERSION"},
            {
                "id": "missing",
                "kind": "FILE_STAT",
                "path": str(
                    Path(tempfile.gettempdir())
                    / "cb_missing_perf005"
                ),
            },
        ])
        self.assertTrue(result["read_only"])
        self.assertTrue(result["complete"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["ok_count"], 1)
        self.assertEqual(result["error_count"], 1)
        self.assertTrue(result["items"][0]["ok"])
        self.assertFalse(result["items"][1]["ok"])
        self.assertEqual(
            result["items"][1]["error_type"],
            "FileNotFoundError",
        )

    def test_file_stat_and_sha256_are_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data.bin"
            content = b"CodeBridge PERF005\x00\xff"
            path.write_bytes(content)
            before = path.stat().st_mtime_ns
            result = rob.execute_read_only_batch([
                {
                    "id": "stat",
                    "kind": "FILE_STAT",
                    "path": str(path),
                },
                {
                    "id": "hash",
                    "kind": "SHA256",
                    "path": str(path),
                },
            ])
            after = path.stat().st_mtime_ns

        self.assertEqual(result["ok_count"], 2)
        self.assertEqual(before, after)
        stat = result["items"][0]["result"]
        digest = result["items"][1]["result"]
        self.assertEqual(stat["size"], len(content))
        self.assertEqual(
            digest["sha256"],
            hashlib.sha256(content).hexdigest(),
        )
        self.assertEqual(digest["size"], len(content))

    def test_git_queries_match_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            env = os.environ.copy()
            env.update({
                "GIT_AUTHOR_NAME": "CodeBridge Test",
                "GIT_AUTHOR_EMAIL": "cb@example.invalid",
                "GIT_COMMITTER_NAME": "CodeBridge Test",
                "GIT_COMMITTER_EMAIL": "cb@example.invalid",
                "GIT_OPTIONAL_LOCKS": "0",
            })
            subprocess.run(
                ["git", "init", "-b", "main", str(repo)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            (repo / "a.txt").write_text(
                "alpha\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(repo), "add", "a.txt"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-m", "init"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            expected_head = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                text=True,
            ).strip()

            result = rob.execute_read_only_batch([
                {"kind": "GIT_STATUS", "path": str(repo)},
                {"kind": "GIT_HEAD", "path": str(repo)},
                {"kind": "GIT_BRANCH", "path": str(repo)},
            ])

        self.assertEqual(result["ok_count"], 3)
        self.assertTrue(
            result["items"][0]["result"]["clean"]
        )
        self.assertEqual(
            result["items"][1]["result"]["head"],
            expected_head,
        )
        self.assertEqual(
            result["items"][2]["result"]["branch"],
            "main",
        )
        self.assertFalse(
            result["items"][2]["result"]["detached"]
        )

    def test_git_path_is_single_argv_and_shell_false(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo;echo INJECTION"
            repo.mkdir()
            fake = SimpleNamespace(
                stdout="## main\n",
                stderr="",
                returncode=0,
            )
            with patch.object(
                rob.subprocess,
                "run",
                return_value=fake,
            ) as run:
                rob._git_status(str(repo))
        args = run.call_args.args[0]
        self.assertIn(str(repo.absolute()), args)
        self.assertEqual(
            args.count(str(repo.absolute())),
            1,
        )
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(args[0], "git")
        self.assertIn("--no-optional-locks", args)


if __name__ == "__main__":
    unittest.main()