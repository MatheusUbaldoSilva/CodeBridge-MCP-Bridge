# RAG-DEL 01.04 DQ-E-F-7 — Loaded Python bytecode vs source witness (DEV)

Root cause addressed: previous offscreen GUI witness F-6 treated the mere presence of function-name tokens in co_names/co_consts as evidence of a loaded pinned reader. An attacker/test fixture could construct a fake _rag_operation with those names while executing a completely different route.

New F-7 read-only verifier compiles a bounded exact on-disk Python source file WITHOUT importing/executing it, looks up exactly one matching top-level code object and compares the loaded CodeType directly, including constants/child code. This intentionally avoids marshal serialization as a byte-level equality metric; marshal outputs were observed to differ for two equal code objects. It also checks absolute source path, file size and rejects symlink/junction paths. No code execution, database read or network activity.

F-6 now requires both the loaded GUI documents-route function and the pinned public reader function to match their respective current DEV source bytes before producing a positive LAB witness. Test with a deliberately forged function carrying the old required name tokens now fails closed.

16 unit tests PASS (F-7 and F-6 combined), including malicious co_names forgery, missing file, invalid root, and no execution. The installed GUI has NOT been probed. Matching a mutable disk file is NOT independent signed code provenance, and NEVER authorizes deletion or production cutover. Preexisting dirty GUI source files remain untouched. No Stable/push or real index/queue mutation.
