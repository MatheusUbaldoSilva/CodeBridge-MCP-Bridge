# RAG-DEL 01.04 DQ-E-F-10 — GUI process creation-order observation (DEV)

New read-only Windows GUI process observer supplements F-8 exact argv checks with OS-observed Win32 CIM CreationEpochMs timestamps and verifies parent creation precedes or equals child creation throughout the selected launcher -> GUI -> MCP lineage. Missing, malformed, boolean, negative or reversed birth timestamps cause fail-closed UNVERIFIED. No actual handle binding, module load query or process mutation occurs.

Seven focused tests PASS, including malicious process chronology, missing/boolean timestamp and stale-parent simulation. A fresh real Win32 CIM snapshot observed a valid chronological launcher/GUI/MCP tree (process_creation_order_observed=true). The installed_gui_runtime_attested and loaded_python_module_attested flags remain explicitly false, as process chronology is NOT proof of module execution. This supplements, but does not replace, a cooperative trusted in-process GUI attestation.

No Stable, installed GUI/MCP, protected existing dirty files, real queues/indexes or GitHub changes.
