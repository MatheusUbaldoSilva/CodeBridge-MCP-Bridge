# RAG-DEL-01.04 DQ-E-F-6 — Qt in-process pinned-reader observer (DEV lab)

Added a read-only helper callable with an existing RagPanel instance on its owning GUI thread. It inspects already-loaded Python modules rather than importing the GUI/reader or executing a query. Checks the panel module and pinned reader source paths, the loaded _rag_operation code path and pinned reader reference, a loaded reader function referring to production_generation_read, QApplication presence and Qt GUI-thread affinity. Creates only a code-byte digest receipt and local PID; never uses an installed GUI IPC socket or mutates an index.

Six offscreen PySide6 tests PASS. A genuine RagPanel fixture was created with refresh mocked to avoid live reads and verified. Unloaded reader, wrong class, wrong root and relative root are denied. The helper itself does not import the reader or execute production_generation_read.

This is evidence from a NEW OFFSCREEN LAB process, not from the existing running CodeBridge GUI. There is no trusted in-process transport for the installed GUI, so installed_gui_trusted_channel_attested=false and gui_runtime_attested_for_operational_deletion=false always. The GUI's existing dirty source files have not been changed. Deletion remains blocked; Stable, live queues, indices and remote GitHub unchanged.
