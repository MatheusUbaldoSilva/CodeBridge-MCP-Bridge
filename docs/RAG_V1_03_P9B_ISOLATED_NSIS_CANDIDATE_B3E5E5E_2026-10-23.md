# P9-B / isolated NSIS candidate and recovery evidence / 2026-10-23

STATUS: CANDIDATE COMPILED; FOUR-ARTIFACT IDENTITY VERIFIED;
P9-B STILL OPEN; REAL INSTALLER NEVER EXECUTED.

## Provenance and build

- Git source commit: b3e5e5e42e5f3650f8fed6824f15da1ddf1939ff
- Git archive: P9B_SOURCE_ONLY_b3e5e5e42e5f.zip
- Source ZIP SHA256: C85D1650169FBFEFCC245C73F03E9FF05A597D659C8F94C0C0A18D164C890E40
- Build happened solely in LOCALAPPDATA/CodeBridge-MCP-Bridge/release_staging
  using the extracted clean source and installed makensis.exe directly.
- No invocation of installer/build_installer.ps1 (copies to Desktop).
- Verified auxiliary tunnel-client.exe and cloudflared.exe source/destination hashes.
- Output: P9B_SOURCE_ONLY_b3e5e5e42e5f_TREE/installer/dist/CodeBridge-Setup.exe
- Binary size: 27280340 bytes; MZ header; file version 2.0.11-prealpha.
- Binary SHA256: B9A6409E809D495D76AB8BFFEDA1BB94A41563539002090F6AFAC20C89FB0C2B.
- No installation, uninstall, process stop, live RAG write or cutover.

## Recovery artifacts bound to candidate hash

Paths below are rooted at LOCALAPPDATA/CodeBridge-MCP-Bridge/release_staging.

- P9B_FILE_ROLLBACK_b3e5e5e42e5f.zip
  SHA256 1ABFD427722A7536A919E8937FCE00C45AF6A83BBF3A806BE56BD603714CD27E
  Verified installer rollback snapshot; 258 candidate file targets,
  236 installed files, 22 missing, 236 baseline files checked and matched.
- P9B_SHELL_ROLLBACK_b3e5e5e42e5f.zip
  SHA256 E9215996F81EB64021ABFAE1046F7E5993F8100D5FED33636C9057994073B5CC7
  Verified 2 HKCU CodeBridge registry keys and 5 scoped shortcuts.
- P9B_CRASH_PREIMAGE_b3e5e5e42e5f.zip
  SHA256 8DCC4012C1337B7C2EA03E6E1C6BF2BD112E2657EBE475A4A053F1114404068A2
  Durable preimage verified, registry read-only, no restore.
- P9B_IDENTITY_b3e5e5e42e5f.json
  SHA256 83BD9ED8561D752CB6956DD3785C59CBFA44109D098F7CD291B13D81F5A2638A0
  Four artifact binding and detached identity contract verified.

The three-way gate returned THREE_WAY_BACKUP_OBSERVED_ONLY,
verified=true and authorized=false.
The detached supervisor invoked through MCP returned
DETACHED_SUPERVISOR_REFUSED / EXTERNAL_ANCESTRY_REQUIRED,
process_ancestry_verified=false and authorized=false.
This is a valid blocker; not a reason to bypass the control.

## Remaining required evidence

1. Independent supervisor process ancestry and durable journal, not controlled
   by the MCP which will be stopped.
2. Tested transactional restoration including installed files, HKCU values,
   start menu and desktop shortcuts, plus crash/replay handling.
3. Fresh snapshot and installed baseline recheck at the authorized cutover.
4. New NSIS process guard after a graceful stop, operator authorization,
   actual controlled install and postupdate verification.
5. Successful CBMCP/1 public reconnect, scheduler/queue and RAG verification.
6. Git diff/review/commit audit and postcommit validation before phase closure.

Do not treat this source or these backup archives as proof of deployability.
No signing/authenticity attestation or production rollback has been certified.
Three preexisting local dirty files remain excluded from source archive.
