import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.sources.git_inventory import (
    GIT_FACET_FIELDS,
    READ_ONLY_GIT_OPERATIONS,
    GitFacet,
    fields_for_git_facet,
    is_read_only_git_operation,
)


class RagGitInventoryTests(unittest.TestCase):
    def test_handoff_git_facets_are_exactly_mapped(self):
        self.assertEqual(
            set(GitFacet),
            {
                GitFacet.BRANCH,
                GitFacet.HEAD,
                GitFacet.COMMIT,
                GitFacet.MESSAGE,
                GitFacet.FILE,
                GitFacet.DIFF,
                GitFacet.HISTORY,
            },
        )

    def test_every_git_facet_has_repository_provenance(self):
        for facet in GitFacet:
            with self.subTest(facet=facet):
                self.assertIn(
                    "repository",
                    fields_for_git_facet(facet),
                )

    def test_commit_and_message_are_commit_anchored(self):
        self.assertIn(
            "commit",
            fields_for_git_facet(GitFacet.COMMIT),
        )
        self.assertIn(
            "commit",
            fields_for_git_facet(GitFacet.MESSAGE),
        )

    def test_file_and_diff_are_path_aware(self):
        self.assertIn(
            "path",
            fields_for_git_facet(GitFacet.FILE),
        )
        self.assertIn(
            "path",
            fields_for_git_facet(GitFacet.DIFF),
        )

    def test_history_is_reference_based_not_raw_repository_copy(self):
        fields = fields_for_git_facet(GitFacet.HISTORY)
        self.assertIn("scope", fields)
        self.assertIn("commit_refs", fields)
        self.assertNotIn("raw_repository", fields)

    def test_only_read_only_git_operations_are_approved(self):
        expected = {
            "status",
            "branch-show-current",
            "rev-parse",
            "log",
            "show",
            "diff",
        }
        self.assertEqual(set(READ_ONLY_GIT_OPERATIONS), expected)
        for operation in expected:
            with self.subTest(operation=operation):
                self.assertTrue(
                    is_read_only_git_operation(operation)
                )

    def test_mutating_git_operations_are_not_approved(self):
        for operation in (
            "add",
            "commit",
            "checkout",
            "switch",
            "reset",
            "restore",
            "merge",
            "rebase",
            "cherry-pick",
            "push",
            "pull",
            "fetch",
            "clean",
            "tag",
            "branch-delete",
        ):
            with self.subTest(operation=operation):
                self.assertFalse(
                    is_read_only_git_operation(operation)
                )

    def test_invalid_facet_is_rejected(self):
        with self.assertRaises(ValueError):
            fields_for_git_facet("HEAD")

    def test_field_map_covers_every_facet_once(self):
        self.assertEqual(
            set(GIT_FACET_FIELDS),
            set(GitFacet),
        )


if __name__ == "__main__":
    unittest.main()
