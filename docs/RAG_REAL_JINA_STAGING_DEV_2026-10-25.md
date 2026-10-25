# Real Jina isolated indexing trial for codebrige-mcp-rag

Date 2026-10-25

## Purpose

Validate one code source and one documentation source end to end through the actual DEV
indexing builder while the installed CodeBridge UI remains gracefully closed

No active RAG generation publication
No modification to the frozen DEV source tree
No alteration to the stable application snapshot

## Input

Project codebrige-mcp-rag
Pinned DEV source 570bb178aa07b8a22471f9f3692ea0db9f6b05a9
Selected app_rewrite/constants.py and manual_tests/README.md
Source is a clean Git archive separate from the working repository

## Initial failure and evidence

The initial test raised ModelLoadError
llama-server exited before ready with Windows exit 3221226505
Text model log recorded CUDA shared object initialization failure

The query time TEXT path worked through its existing GPU to CPU fallback manager
The staging TEXT path initially loaded TextModelLifecycle directly
The staging path was changed to use TextModelFallbackManager.auto
The same tested bounded context 8192 and ubatch 512 are kept
The model is unloaded after embedding whether it runs on GPU or CPU

## Second failure

The text model indexed its documentation
The CODE model initialized and processed its first fragment
Then code embedding returned HTTP 500
llama.cpp CODE log revealed failure to allocate a 35605504 byte output buffer
This occurred with internal ubatch 128 and one 2048 context slot

The indexing only ubatch is now 32
The query time CODE ubatch stays 128
No change to pinned model artifacts or CodeBridge search settings

## Final real trial

Third real trial completed successfully

Two documents
Seven chunks total
Four DOCUMENTATION text chunks
Three CODE chunks

SQLite and Qdrant staging both validated by validate_staged_index
Additional read only cross checks compared all seven Qdrant payloads to SQLite chunk IDs and contents
Text vector dimension 1024
Code vector dimension 1536
Self nearest neighbor query returned score 1 for both collections
All vectors belong to namespace codebrige-mcp-rag

Real staging location

C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\staging\build-8ac8d9b6c91a41f993f0ba6d674888d7

Structured evidence location

C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\real-jina-small-batch-result-lowbatch.json

Previous failure evidence remains in distinct JSON files
Successful test duration 36 seconds

## Regression tests

tests/test_rag_text_index_fallback.py verifies no model side effects and fallback cleanup
tests/test_rag_production_code_cpu_fallback_integration.py now confirms index CODE ubatch setting
Original bounded chunk and staged index tests passed again
The full source corpus validation before this trial found 965 eligible files producing 11320 bounded chunks

## Production guard

Active generation before and after each trial remained v1_delta_1ae1d01ea84f4e
The live index was not overwritten
The new project label is registered but the full corpus is not indexed or available via public MCP
No source files were deleted
DEV Git change is independent of stable

## Remaining

Full 965 source indexing remains unexecuted
Do not infer total run time from the tiny sample because 11320 embeddings is much larger
Full indexing needs staged batching and further memory monitoring
Publication requires the existing generation authorization and rollback checks
The stale source get_context issue discovered during earlier audit remains a separate outstanding correction
