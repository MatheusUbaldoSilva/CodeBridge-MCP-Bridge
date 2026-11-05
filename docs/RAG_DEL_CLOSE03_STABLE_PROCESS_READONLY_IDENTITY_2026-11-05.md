# CLOSE-03 — Stable Candidate process identity snapshot (read-only)

Date: 2026-11-05 | DEV branch: dev-local

## Process evidence

- PID: 2152; parent PID: 6760.
- Image: python.exe at CodeBridge-Runtime/stable-candidate-570bb17/Scripts/python.exe.
- Command line: stable-candidate-570bb17/app_rewrite/main.py --no-elevate.
- Process creation: 2026-11-05 09:14:58 local Windows time.
- Interpreter SHA-256: 72B29481593C5DA37C99248C82777FBFB56217EA7809B771BC760D0A9ECB179B.
- Snapshot version: 2.0.11-prealpha (windows_file_version 2.0.11.0).
- Stable snapshot source hashes: main.py 02B5A756C7377D66A0C4E47D7E3929AE2F51D166346CB9FAB54A21F7608794D3; rag_panel.py F4728B357E11244F58683B673BDBB9834F63E42D85D6F4EE48C70EB3AF820C68; ipc_named_pipe.py 67D8A8ACFA1AD1FC96E79706A9E8B4B490002B2FB783E74AE741803DC1D1B54D.
- The snapshot directory is not a Git worktree. The source-file hashes are on-disk snapshot evidence only.
- Process module enumeration exposed the Python interpreter and core Windows DLLs; it did not establish Python-level loaded module paths or prove which .py/.pyc objects are resident.

## Interpretation and boundary

This confirms that the visible desktop process is the Stable Candidate snapshot, not the dev-local worktree. It is not an installed-GUI loaded-code attestation and does not prove the connected operational Named Pipe peer token. No process injection, debugger attach, restart, source mutation, Stable rollout, queue/canary/catalog/generation change, or GitHub push occurred.

The KEEP decision for newworldpvp remains in force. CLOSE-03 G32 remains blocked; production deletion remains disabled.

