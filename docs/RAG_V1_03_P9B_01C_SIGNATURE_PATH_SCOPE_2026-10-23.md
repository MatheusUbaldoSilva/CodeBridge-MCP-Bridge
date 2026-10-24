# P9-B.01-C - Signature path containment
Status: verifier tightened, trust root STILL UNVERIFIED.
Change: detached Ed25519 signature must be an ordinary 64-byte file inside disposable TEMP scope, without symlink. External and symlinked signature locations fail before reading their bytes. Existing bundle validity gates remain unchanged. The caller must not substitute its own alleged trusted-root attestation.
Verification: eight signature tests PASS, 552 full P9B PASS in 53.887 seconds.
Not a production certificate, and does not authorize NSIS/official cutover.