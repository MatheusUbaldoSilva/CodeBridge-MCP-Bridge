# P9-B.01-D - Adversarial consistency tests
State: lab consistency negative tests PASS; 01-D not certified until protected trust root is integrated. P9-B OPEN.

The TEMP-only frozen bundle now checks lexical symlink ancestry as well as resolved containment, rejecting a redirected parent of installed/appdata/desktop or one of the four input artifacts. Current tests also deny forged manifest plus matching hash when scopes escape TEMP, duplicate JSON key, modified frozen artifact, malformed ID, broad HKCU prefix and inappropriate temp_root enlargement.

Ed25519 verification tests reject wrong signature and wrong key. Caller-supplied trust attestation is never accepted for cutover. Source authenticity still unproven: TRUST_ROOT_UNVERIFIED.

Evidence: 14 focused frozen bundle tests PASS, six signature tests PASS; full P9B 534 PASS in 51.675 seconds.
Production installer did not run. Existing installed CodeBridge, official HKCU, RAG, MCP and gates authorized=False unchanged.

Next: establish genuine protected trust root for 01-C; then repeat 01-D with authorized source identity, malicious package/reparse, source-commit substitution and TOCTOU during worker consumption before claiming 01 complete.