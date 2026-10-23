# P9-B / Windows Scheduled Task read-only independence attestation

Date: 2026-10-23
Status: READ-ONLY EXTERNAL ANCESTRY VERIFIED. P9-B remains OPEN.

## Recovering the connection

The CodeBridge CBMCP/1 endpoint recovered to READY with PowerShell,
CMD and SSH terminals online. The public RAG index is still READY in
generation v1_delta_1ae1d01ea84f4e, with 211 documents and 8774 chunks.

## Exact candidate and identity

Staging NSIS executable source commit:
b3e5e5e42e5f3650f8fed6824f15da1ddf1939ff
Executable SHA256:
B9A6409E809D495D76AB8BFFEDA1BB94A41563539002090F6AFAC20C89FB0C2B

Bound identity:
P9B_IDENTITY_b3e5e5e42e5f.json
SHA256 83BD9ED8561D752CB6956DD3785C59CBFA44109D098F7CD291B13D81F5A2638A0

Four artifact digests rechecked successfully against the identity manifest.
The standalone identity gate returned DETACHED_IDENTITY_OBSERVED_ONLY
with identity_verified=true. Running the supervisor through CodeBridge
returned EXTERNAL_ANCESTRY_REQUIRED, correctly denying cutover.

## External process attestation without mutation

An isolated stage P9B_B3E5E5E_DETACHED_READONLY was constructed beneath
LOCALAPPDATA/CodeBridge-MCP-Bridge/release_staging with a hash-identical
TRANSACTION_IDENTITY.json and staged independent psutil dependency.

The project's p9b_scheduled_readonly_launcher.ps1 launched a disposable
Windows Scheduled Task, independent from CodeBridge process ancestry.

Result: SCHEDULED_READONLY_LAUNCH_VERIFIED
- authorized: false
- installer_executed: false
- shutdown_signals_sent: false
- read_only: true
- source commit: b3e5e5e42e5f3650f8fed6824f15da1ddf1939ff
- identity SHA256: 83bd9ed8561d752cb6956dd3785c59cbfa4109d098f7cd291b13d81f5a2638a0

After the run:
- Temporary scheduled task absent
- Temporary worker folders absent
- Git source and upstream equal
- Three historical dirty local files remain preserved

## Limit of this evidence

A detached read-only scheduled inspection has succeeded. No live MCP or
GUI process was stopped, no actual NSIS installation or rollback occurred,
and no postupdate CBMCP/1 reconnection was certified.

Do not convert this result into permission to update production.
Next: certify durable independent mutating supervisor with crash replay,
full file + HKCU + shortcut rollback, and postrestore evidence in a
disposable test installation first. Only then plan an operator-authorized
live cutover with a fresh rollback baseline and RAG verification.
