"""RAG-DEL-01.05: UI-facing read-only deletion review, no mutation capability."""
from __future__ import annotations
from rag.runtime.knowledge_deletion_preview import preview_knowledge_removal

class DeletionReviewError(ValueError):
    pass

def build_deletion_review(project_id: str, selected_paths: list[str]) -> dict:
    if not isinstance(project_id,str) or project_id=="codebridge" or not project_id:
        raise DeletionReviewError("Apenas projeto privado isolado pode ser revisado")
    if (not isinstance(selected_paths,list) or not selected_paths
            or len(set(selected_paths))!=len(selected_paths)):
        raise DeletionReviewError("Selecione arquivos únicos para a revisão")
    preview=preview_knowledge_removal(project_id,sorted(selected_paths))
    if (preview.get("project_id")!=project_id
            or preview.get("selected_paths")!=sorted(selected_paths)
            or preview.get("deletion_authorized") is not False
            or preview.get("candidate_created") is not False
            or preview.get("public_pointer_updated") is not False):
        raise DeletionReviewError("Prévia inválida ou não isolada")
    count=preview["documents_to_remove"]
    chunks=preview["chunks_to_remove"]
    remaining=preview["documents_to_preserve"]
    review_sha=preview["review_sha256"]
    return {
        "state":"READ_ONLY_REVIEW",
        "project_id":project_id,"generation":preview["generation"],
        "source_revision":preview["source_revision"],
        "selected_paths":preview["selected_paths"],
        "review_sha256":review_sha,
        "documents_to_remove":count,
        "chunks_to_remove":chunks,
        "documents_to_preserve":remaining,
        "display_text":(
            f"Projeto: {project_id}\n"
            f"Geração: {preview['generation']}\n"
            f"Arquivos selecionados: {count}\n"
            f"Chunks que sairiam: {chunks}\n"
            f"Arquivos preservados: {remaining}\n"
            f"Identificador da revisão: {review_sha}\n\n"
            "SIMULAÇÃO: nenhum conhecimento foi removido."
        ),
        "execution_enabled":False,
        "source_files_modified":False,
    }
