# RAG-DEL-01.04 DQ-E-D-3C-G-11 — Scratch MAC child timeout/kill

The lab parent now supports an enumerated hang-fixture mode. This fixture never responds to the anonymous pipe; the parent enforces the requested bounded timeout, kills and reaps the subprocess and raises a non-authorizing error. Subsequent normal scratch and real-worker handshakes still succeed.

Three new tests PASS (seven targeted including G-9). The fixture has no access to real projects, models, SQLite, Qdrant, deletion or production queue. This is not a production cancellation implementation. Real worker and Stable unchanged, no GitHub push.
