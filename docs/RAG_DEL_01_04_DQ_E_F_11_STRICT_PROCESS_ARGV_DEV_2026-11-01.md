# RAG-DEL 01.04 DQ-E-F-11 - Strict DEV GUI/MCP process argv contract (2026-11-01)

## Purpose
Prevent false-positive read-only process-topology evidence when a Windows
command line contains a valid argument pair plus a duplicate, conflicting,
shadowed or unparsed argument. The prior F-8 diagnostic checked for the
presence of required argv entries but accepted other tokens. This phase
makes observations stricter; it does not prove what the installed process
loaded, grant permissions or implement deletion.

## DEV-only change
- Launcher: python[w].exe launcher.py with no extra tokens.
- GUI: python[w].exe app_rewrite/main.py --no-elevate.
- MCP: python[w].exe author_mcp/mcp_server.py --host 127.0.0.1 --port 8765,
  in either order.
- Required flags appear exactly once. --port and --host cannot be shadowed
  with --flag=value, duplicated, replaced or placed after --.
- Unknown positional or option tokens fail closed.
- F-10 creation-order diagnostic shares the stricter MCP specification.
  F-9 and F-10 test fixtures aligned with actual DEV launch arguments.

## Safety boundary
This is OS command-line metadata only. It does not authenticate installed
GUI modules, prove CLI parser behavior or constitute challenge/response.
No new attestation channel, IPC permission change, live queue/journal/index
access, deletion, installed GUI/MCP or Stable update, or GitHub push.
activation_authorized=false and operational_use_allowed=false remain.
G32 and F-9 security limitations remain.

## Verification protocol
Run focused F-8/F-9/F-10/F-11 unit tests, optionally observe read-only
Win32 process snapshot for exact launcher/GUI/MCP argv, and run
RAG-DEL and related regressions. Audit scoped diff and preserve all
five preexisting dirty files exactly.

## Verified results (DEV)
- Focused F-8 + F-10: 30 PASS after 10 added F-11 adversarial tests.
- F-9 offscreen trust-boundary: 7 PASS.
- Real read-only Win32 CIM snapshot: 5 DEV process records,
  launcher=1, GUI=2, MCP=2, argv contract positive and birth order positive;
  installed GUI modules NOT attested and operational authorization FALSE.
- Complete RAG-DEL: 667 tests, 661 PASS, 6 SKIP, 0 FAIL.
- RAG-AUTO non-MCP: 241 tests, 236 PASS, 5 SKIP, 0 FAIL.
- MCP: 12 PASS, 0 FAIL.
- Aggregate: 920 tests, 909 PASS, 11 SKIP, 0 FAIL.
- Qt font directory warning is environmental, not a failed test.

DEV source only; installed GUI/prod deletion approval remains UNVERIFIED.
