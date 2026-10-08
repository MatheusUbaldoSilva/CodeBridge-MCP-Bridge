from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qdrant_client import models

from rag.benchmark.corpus import build_lexical_benchmark_index
from rag.benchmark.metrics import (
    current_process_rss_bytes,
    current_vram_used_mib,
    directory_size_bytes,
    evaluate_ranked_paths,
    process_rss_bytes,
)
from rag.contracts import SearchQuery
from rag.index.qdrant_local import (
    CODE_VECTOR_COLLECTION,
    TEXT_VECTOR_COLLECTION,
    close_qdrant_local,
    ensure_vector_collections,
    open_qdrant_local,
)
from rag.index.vector_ids import deterministic_vector_point_id
from rag.index.vector_namespace import vector_payload_with_namespace
from rag.models.artifact_install import resolve_selected_model_path
from rag.models.code_artifact_install import resolve_selected_code_model_path
from rag.models.code_embedding import CodeEmbeddingClient, CodeRetrievalTask
from rag.models.code_lifecycle import CodeModelLifecycle, build_code_server_config
from rag.models.embedding import TextEmbeddingClient
from rag.models.lifecycle import LlamaServerConfig, TextModelLifecycle
from rag.ranking.dedup import deduplicate_ranked_results
from rag.ranking.rrf import reciprocal_rank_fusion
from rag.retrieval.hybrid_code import collect_code_hybrid_candidates
from rag.retrieval.hybrid_query import collect_hybrid_query_candidates
from rag.retrieval.hybrid_text import collect_text_hybrid_candidates
from rag.runtime.query_classifier import QueryRoute, classify_query


DATASET = ROOT / "benchmarks" / "rag014_dataset.jsonl"
GROUND_TRUTH = ROOT / "benchmarks" / "rag014_ground_truth.jsonl"
OUTPUT = ROOT / "benchmarks" / "rag014_semantic_benchmark_latest.json"
LLAMA_SERVER = Path(r"C:\llama\llama-server.exe")
PROJECT_ID = "codebridge"
BATCH_SIZE = 64


def _jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _chunk_rows(connection: sqlite3.Connection, source_type: str):
    return connection.execute(
        """
        SELECT
            chunk_id,
            document_id,
            content,
            source_type,
            path,
            line_start,
            line_end,
            sha256
        FROM rag_chunks
        WHERE source_type = ?
        ORDER BY document_id, ordinal, chunk_id
        """,
        (source_type,),
    ).fetchall()


def _payload(row):
    return {
        "document_id": str(row[1]),
        "content": str(row[2]),
        "source_type": str(row[3]),
        "path": row[4],
        "line_start": row[5],
        "line_end": row[6],
        "sha256": row[7],
    }


def _batch_upsert(client, collection_name, items):
    points = []
    for row, vector in items:
        payload = vector_payload_with_namespace(
            PROJECT_ID,
            _payload(row),
        )
        payload["chunk_id"] = str(row[0])
        points.append(
            models.PointStruct(
                id=deterministic_vector_point_id(
                    PROJECT_ID,
                    collection_name,
                    str(row[0]),
                ),
                vector=list(vector),
                payload=payload,
            )
        )
    client.upsert(
        collection_name=collection_name,
        points=points,
        wait=True,
    )


def _index_text_vectors(connection, qdrant):
    rows = _chunk_rows(connection, "DOCUMENTATION")
    life = TextModelLifecycle(
        LlamaServerConfig(
            executable_path=LLAMA_SERVER,
            model_path=resolve_selected_model_path(),
            port=0,
            gpu_layers=99,
            device="CUDA0",
        )
    )
    vram_before = current_vram_used_mib()
    load_started = time.perf_counter()
    snap = life.load(timeout_seconds=90)
    load_ms = (time.perf_counter() - load_started) * 1000.0
    client = TextEmbeddingClient(life)
    peak_rss = process_rss_bytes(int(snap.pid))
    vram_loaded = current_vram_used_mib()
    started = time.perf_counter()
    batch = []
    try:
        for index, row in enumerate(rows, 1):
            vector = client.embed_document(str(row[2])).values
            batch.append((row, vector))
            if len(batch) >= BATCH_SIZE:
                _batch_upsert(qdrant, TEXT_VECTOR_COLLECTION, batch)
                batch.clear()
            if index % 250 == 0 or index == len(rows):
                peak_rss = max(peak_rss, process_rss_bytes(int(snap.pid)))
                print(f"TEXT_INDEX {index}/{len(rows)}", flush=True)
        if batch:
            _batch_upsert(qdrant, TEXT_VECTOR_COLLECTION, batch)
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        life.unload(timeout_seconds=15)
    vram_after = current_vram_used_mib()
    return {
        "chunks": len(rows),
        "model_load_ms": load_ms,
        "embedding_and_upsert_ms": elapsed_ms,
        "llama_peak_rss_bytes": peak_rss,
        "vram_before_mib": vram_before,
        "vram_loaded_mib": vram_loaded,
        "vram_after_mib": vram_after,
        "vram_delta_mib": (
            None
            if vram_before is None or vram_loaded is None
            else vram_loaded - vram_before
        ),
    }


def _index_code_vectors(connection, qdrant):
    rows = _chunk_rows(connection, "CODE")
    life = CodeModelLifecycle(
        build_code_server_config(
            executable_path=LLAMA_SERVER,
            model_path=resolve_selected_code_model_path(),
            port=0,
            gpu_layers=99,
            device="CUDA0",
        )
    )
    vram_before = current_vram_used_mib()
    load_started = time.perf_counter()
    snap = life.load(timeout_seconds=90)
    load_ms = (time.perf_counter() - load_started) * 1000.0
    client = CodeEmbeddingClient(life)
    peak_rss = process_rss_bytes(int(snap.pid))
    vram_loaded = current_vram_used_mib()
    started = time.perf_counter()
    batch = []
    try:
        for index, row in enumerate(rows, 1):
            vector = client.embed_passage(
                CodeRetrievalTask.NL2CODE,
                str(row[2]),
            ).values
            batch.append((row, vector))
            if len(batch) >= BATCH_SIZE:
                _batch_upsert(qdrant, CODE_VECTOR_COLLECTION, batch)
                batch.clear()
            if index % 100 == 0 or index == len(rows):
                peak_rss = max(peak_rss, process_rss_bytes(int(snap.pid)))
                print(f"CODE_INDEX {index}/{len(rows)}", flush=True)
        if batch:
            _batch_upsert(qdrant, CODE_VECTOR_COLLECTION, batch)
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        life.unload(timeout_seconds=15)
    vram_after = current_vram_used_mib()
    return {
        "chunks": len(rows),
        "model_load_ms": load_ms,
        "embedding_and_upsert_ms": elapsed_ms,
        "llama_peak_rss_bytes": peak_rss,
        "vram_before_mib": vram_before,
        "vram_loaded_mib": vram_loaded,
        "vram_after_mib": vram_after,
        "vram_delta_mib": (
            None
            if vram_before is None or vram_loaded is None
            else vram_loaded - vram_before
        ),
    }


def _embed_text_queries(dataset):
    wanted = [
        row for row in dataset
        if classify_query(row["query"]).route in {QueryRoute.TEXT, QueryRoute.HYBRID}
    ]
    life = TextModelLifecycle(
        LlamaServerConfig(
            executable_path=LLAMA_SERVER,
            model_path=resolve_selected_model_path(),
            port=0,
            gpu_layers=99,
            device="CUDA0",
        )
    )
    started = time.perf_counter()
    snap = life.load(timeout_seconds=90)
    load_ms = (time.perf_counter() - started) * 1000.0
    client = TextEmbeddingClient(life)
    vectors = {}
    timings = {}
    peak_rss = process_rss_bytes(int(snap.pid))
    try:
        for row in wanted:
            t = time.perf_counter()
            vectors[row["id"]] = client.embed_query(row["query"]).values
            timings[row["id"]] = (time.perf_counter() - t) * 1000.0
        peak_rss = max(peak_rss, process_rss_bytes(int(snap.pid)))
    finally:
        life.unload(timeout_seconds=15)
    return vectors, timings, load_ms, peak_rss


def _embed_code_queries(dataset):
    wanted = [
        row for row in dataset
        if classify_query(row["query"]).route in {QueryRoute.CODE, QueryRoute.HYBRID}
    ]
    life = CodeModelLifecycle(
        build_code_server_config(
            executable_path=LLAMA_SERVER,
            model_path=resolve_selected_code_model_path(),
            port=0,
            gpu_layers=99,
            device="CUDA0",
        )
    )
    started = time.perf_counter()
    snap = life.load(timeout_seconds=90)
    load_ms = (time.perf_counter() - started) * 1000.0
    client = CodeEmbeddingClient(life)
    vectors = {}
    timings = {}
    peak_rss = process_rss_bytes(int(snap.pid))
    try:
        for row in wanted:
            t = time.perf_counter()
            vectors[row["id"]] = client.embed_query(
                CodeRetrievalTask.NL2CODE,
                row["query"],
            ).values
            timings[row["id"]] = (time.perf_counter() - t) * 1000.0
        peak_rss = max(peak_rss, process_rss_bytes(int(snap.pid)))
    finally:
        life.unload(timeout_seconds=15)
    return vectors, timings, load_ms, peak_rss


def _rank_query(connection, qdrant, row, text_vectors, code_vectors):
    route = classify_query(row["query"]).route
    query = SearchQuery(
        query=row["query"],
        project_id=PROJECT_ID,
        top_k=10,
    )
    if route is QueryRoute.TEXT:
        candidates = collect_text_hybrid_candidates(
            connection,
            qdrant,
            query,
            text_vectors[row["id"]],
        )
        fused = reciprocal_rank_fusion(
            (candidates.lexical, candidates.vector),
            top_k=20,
        )
    elif route is QueryRoute.CODE:
        candidates = collect_code_hybrid_candidates(
            connection,
            qdrant,
            query,
            code_vectors[row["id"]],
        )
        fused = reciprocal_rank_fusion(
            (candidates.lexical, candidates.vector),
            top_k=20,
        )
    elif route is QueryRoute.HYBRID:
        candidates = collect_hybrid_query_candidates(
            connection,
            qdrant,
            query,
            route=QueryRoute.HYBRID,
            text_query_vector=text_vectors[row["id"]],
            code_query_vector=code_vectors[row["id"]],
        )
        fused = reciprocal_rank_fusion(
            (
                candidates.lexical,
                candidates.text_vector,
                candidates.code_vector,
            ),
            top_k=30,
        )
    else:
        raise RuntimeError(f"unsupported benchmark route: {route}")

    final = deduplicate_ranked_results(
        fused,
        top_k=10,
    ).results
    return route, final


def main():
    dataset = _jsonl(DATASET)
    truth_rows = _jsonl(GROUND_TRUTH)
    expected = {
        row["id"]: tuple(row["expected_paths"])
        for row in truth_rows
    }

    with tempfile.TemporaryDirectory(prefix="codebridge-rag014-semantic-") as td:
        temp = Path(td)
        db = temp / "rag014.sqlite3"
        qdrant_path = temp / "qdrant"

        build_started = time.perf_counter()
        corpus = build_lexical_benchmark_index(ROOT, db)
        corpus_build_ms = (time.perf_counter() - build_started) * 1000.0
        connection = sqlite3.connect(str(db))
        qdrant = open_qdrant_local(qdrant_path)
        ensure_vector_collections(qdrant)

        try:
            print("SEMANTIC_INDEX_TEXT_BEGIN", flush=True)
            text_index = _index_text_vectors(connection, qdrant)
            print("SEMANTIC_INDEX_CODE_BEGIN", flush=True)
            code_index = _index_code_vectors(connection, qdrant)

            print("QUERY_EMBED_TEXT_BEGIN", flush=True)
            text_vectors, text_times, text_load_ms, text_query_rss = _embed_text_queries(dataset)
            print("QUERY_EMBED_CODE_BEGIN", flush=True)
            code_vectors, code_times, code_load_ms, code_query_rss = _embed_code_queries(dataset)

            ranked_paths = {}
            retrieval_ms = {}
            routes = {}
            end_to_end_warm_ms = {}

            for index, row in enumerate(dataset, 1):
                t = time.perf_counter()
                route, final = _rank_query(
                    connection,
                    qdrant,
                    row,
                    text_vectors,
                    code_vectors,
                )
                retrieval = (time.perf_counter() - t) * 1000.0
                retrieval_ms[row["id"]] = retrieval
                routes[row["id"]] = route.value
                ranked_paths[row["id"]] = tuple(
                    item.metadata.path or ""
                    for item in final
                )
                embed_ms = 0.0
                if row["id"] in text_times:
                    embed_ms += text_times[row["id"]]
                if row["id"] in code_times:
                    embed_ms += code_times[row["id"]]
                end_to_end_warm_ms[row["id"]] = embed_ms + retrieval
                if index % 20 == 0:
                    print(f"QUERY {index}/{len(dataset)}", flush=True)

            metrics = evaluate_ranked_paths(ranked_paths, expected)
            warm_values = list(end_to_end_warm_ms.values())
            warm_sorted = sorted(warm_values)
            p95 = warm_sorted[max(0, int(len(warm_sorted) * 0.95) - 1)]

            first = dataset[0]
            first_route = QueryRoute(routes[first["id"]])
            first_load_ms = (
                code_load_ms
                if first_route is QueryRoute.CODE
                else text_load_ms
            )
            if first_route is QueryRoute.HYBRID:
                first_load_ms = text_load_ms + code_load_ms

            first_embed_ms = (
                text_times.get(first["id"], 0.0)
                + code_times.get(first["id"], 0.0)
            )
            cold_estimate_ms = (
                first_load_ms
                + first_embed_ms
                + retrieval_ms[first["id"]]
            )

            result = {
                "benchmark": "RAG-014-C_SEMANTIC_REAL",
                "query_count": len(dataset),
                "corpus": {
                    "documents": corpus.documents,
                    "chunks": corpus.chunks,
                    "denied": corpus.denied,
                    "unsupported": corpus.unsupported,
                    "build_ms": corpus_build_ms,
                },
                "routes": {
                    route: list(routes.values()).count(route)
                    for route in sorted(set(routes.values()))
                },
                "metrics": metrics.to_dict(),
                "latency": {
                    "cold_estimate_ms": cold_estimate_ms,
                    "cold_definition": (
                        "first query route model load + query embedding + retrieval"
                    ),
                    "warm_mean_ms": statistics.fmean(warm_values),
                    "warm_median_ms": statistics.median(warm_values),
                    "warm_p95_ms": p95,
                    "retrieval_mean_ms": statistics.fmean(retrieval_ms.values()),
                    "text_query_embedding_mean_ms": (
                        statistics.fmean(text_times.values())
                        if text_times else None
                    ),
                    "code_query_embedding_mean_ms": (
                        statistics.fmean(code_times.values())
                        if code_times else None
                    ),
                    "text_model_load_ms": text_load_ms,
                    "code_model_load_ms": code_load_ms,
                    "hybrid_note": (
                        "warm HYBRID sums both query embeddings and retrieval; "
                        "model switch/load penalty is reported separately"
                    ),
                },
                "resources": {
                    "python_rss_bytes": current_process_rss_bytes(),
                    "llama_peak_rss_bytes": max(
                        text_index["llama_peak_rss_bytes"],
                        code_index["llama_peak_rss_bytes"],
                        text_query_rss,
                        code_query_rss,
                    ),
                    "max_vram_delta_mib": max(
                        value
                        for value in (
                            text_index["vram_delta_mib"],
                            code_index["vram_delta_mib"],
                        )
                        if value is not None
                    ),
                    "sqlite_size_bytes": directory_size_bytes(db),
                    "qdrant_size_bytes": directory_size_bytes(qdrant_path),
                    "total_index_size_bytes": (
                        directory_size_bytes(db)
                        + directory_size_bytes(qdrant_path)
                    ),
                },
                "text_index": text_index,
                "code_index": code_index,
                "top10_paths": {
                    key: list(value)
                    for key, value in ranked_paths.items()
                },
            }
            rendered = json.dumps(result, indent=2, ensure_ascii=False)
            OUTPUT.write_text(rendered + "\n", encoding="utf-8")
            print(rendered)
        finally:
            connection.close()
            close_qdrant_local(qdrant)


if __name__ == "__main__":
    main()
