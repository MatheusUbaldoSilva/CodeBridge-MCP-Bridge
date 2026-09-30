# Manual integration tests

These scripts exercise a live CodeBridge runtime, real terminal processes, or
the managed MCP lifecycle. They are intentionally outside the tests directory
so python -m unittest discover -s tests remains deterministic and cannot stop
or replace the currently running CodeBridge instance.

Run them explicitly when live integration coverage is required:

- python manual_tests/managed_author_mcp_all_targets.py
- python manual_tests/managed_author_mcp_lifecycle.py
- python manual_tests/v2_all_targets_local.py
- python manual_tests/v2_cancel_effects.py
- author_mcp/.venv/Scripts/python.exe manual_tests/author_mcp_v2_all_targets.py
