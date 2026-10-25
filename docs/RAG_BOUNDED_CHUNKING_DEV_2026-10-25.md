# RAG Bounded Chunk Indexing DEV

Date 2026-10-25
Status steps 1 to 5 verified
Step 6 real Jina embedding remains pending

## Why

A fresh full DEV code snapshot contains 965 eligible files
The previous indexing draft pipeline yielded 8496 chunks
21 original chunks exceeded 6000 characters
A minified xterm.js chunk contained 488472 characters
Unbounded source lines could exceed the Jina input budget during real indexing

## Fix

rag/chunking/bounded.py adds a reusable deterministic postprocessor
It runs after the existing semantic chunkers
Small chunks retain the same original content
Large chunks are subdivided at source line boundaries when possible
A long single source line is divided by character offsets
Each piece preserves content exactly within its original chunk
The original paths and 1 based source line coordinates are retained
Column offsets for same line pieces are not currently part of the SQLite schema
The algorithm fails closed when it cannot represent oversized whitespace only content without loss

Maximum chunk lengths used during indexing
CODE 1024 characters
TEXT 2048 characters

The values are conservative character guards and do not prove exact tokenizer size for arbitrary UTF8 inputs

rag/runtime/production_index.py uses this postprocessor for both code and text
This single builder is used for full staging and by incremental_offline_worker

The staging builder now loads models using bounded llama.cpp settings

Jina TEXT context 8192 ubatch 512 parallel 1
Jina CODE context 2048 ubatch 128 parallel 1
Existing GPU code fallback is preserved
Model revisions remain unchanged

## Full snapshot validation

Source project codebrige-mcp-rag
Source commit 570bb178aa07b8a22471f9f3692ea0db9f6b05a9
Source location C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\source-dev-570bb17

Eligible files 965
CODE eligible 949
TEXT eligible 16
Original chunks 8496
Bounded chunks 11320
Bounded CODE chunks 11182
Bounded TEXT chunks 138
Source files with at least one oversized original chunk 586
Largest final chunk 1141 characters
Validation errors 0
No lost original chunk contents detected
No invalid ordinals or line ranges detected
No real vector embeddings built in this validation

Validation JSON
C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\bounded-validation.json

## Tests

tests/test_rag_bounded_index_chunks.py
tests/test_rag_bounded_staging.py

Tests cover
Large single line
Large Python function
Markdown and logs
Fallback continuation
Small unchanged chunk
Invalid size
Whitespace fail closed
Isolated staging SQLite complete source chunk contents with mocked embeddings

Existing staging security tests and incremental worker tests were rerun
Real Jina GPU execution with the new indexer is NOT yet verified

## Safety

The live RAG generation v1_delta_1ae1d01ea84f4e was not modified
The stable application snapshot at 570bb17 was not modified
No changes to GitHub branches
Three preexisting dirty or untracked files were left untouched
Publishing to the live RAG is not covered by this change
New uploaded documents will be bounded when their path reaches build_staged_index
Automatic upload and publication are still subject to existing disabled authorization gates

## Next test gate

Free system memory with a graceful shutdown of the app when authorized
Verify both Jina models with one small approved code file and one markdown file
Write only to an isolated staging directory
Validate SQLite and Qdrant counts and a semantic query against the isolated generation
Only after explicit review proceed to all 965 DEV files
