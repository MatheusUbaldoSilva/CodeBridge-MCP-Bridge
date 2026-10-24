# P9-B.02-B - Read-only disposable scope preflight
Status: lab preflight PASS; 02-B NOT a recovery or production certificate; P9-B OPEN.

Reuse: rag_p9b_frozen_disposable_bundle consistency verification, Windows existing inspect_shell_scope/APP_KEYS/MENU_LINKS/DESKTOP_LINK definitions. New read-only assessor binds installed, appdata, desktop to same frozen manifest, requires injected isolated HKCU query and observes five shortcuts and two remapped registry keys. No default winreg access, no NSIS, no mutation.

Refuses mismatched installed/desktop roots, missing isolated registry query, changed bundle and symlinked parent in shortcut path. Seven focused tests PASS. Full P9B 550 PASS in 52.589 seconds. This does not bypass P9-B.01-C TRUST_ROOT_UNVERIFIED or authorize unified execution.

Files: installer/rag_p9b_disposable_scope_preflight.py; tests/test_rag_p9b_disposable_scope_preflight.py. Historic dirty files excluded. P9-B.02-C/D/E await trusted source and independent scheduled transaction.