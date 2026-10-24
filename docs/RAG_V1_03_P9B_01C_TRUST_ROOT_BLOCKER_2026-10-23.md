# P9-B.01-C - Independent trust-root blocker
Status: signature verification implemented, TRUST_ROOT_UNVERIFIED; NOT CLOSED.

The cryptography package is present. New read-only gate verifies Ed25519 detached signature over all bytes of a frozen disposable manifest, after verifying manifest digest and each of four frozen artifacts.

Negative proofs: forged caller-supplied independent/protected/authorized attestation does NOT unlock; wrong public key, wrong signature, changed manifest, changed artifact refuse. Valid signature math by a caller-controlled public key is not publisher authentication.

Protected root: no independently provisioned protected public-key store, vendor certificate/PKI, access-controlled service or external authorized verifier has yet been proven on this Windows host. No current result may claim source authenticity or enable production installation.

Unlock condition: integrate a protected, auditable trust anchor outside mutable bundle/request/repo control, require proof of publisher identity and authorized purpose; test both forged source and key substitution; add controls for revocation/rotation. Until then P9-B.01-C is BLOCKED and full P9-B remains OPEN.

Files: installer/rag_p9b_trusted_bundle_gate.py; tests/test_rag_p9b_trusted_bundle_gate.py.
All operations read-only; official NSIS and RAG unchanged.