import time
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.repository import (
    RepoCloneRequest,
    RepoCloneResponse,
    RepoFileMetadata,
    RepoIndexResponse,
    RepoScanResponse,
    RepoSecretsAuditResponse,
    SandboxCleanupResponse,
    SecretFindingAudit,
)
from app.schemas.retrieval import HybridSearchQuery, HybridSearchResponse
from app.services.embedding_service import embedding_service
from app.services.file_filter import file_filter_service
from app.services.git_cloner import git_cloner_service
from app.services.hybrid_retriever import hybrid_retriever_service
from app.services.sandbox_manager import sandbox_manager
from app.services.secrets_sanitizer import secrets_sanitizer_service
from app.services.semantic_chunker import semantic_chunker_service
from app.services.vector_store import vector_store_service

router = APIRouter()


@router.post(
    "/clone",
    response_model=RepoCloneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone Repository to Ephemeral Sandbox",
    description="Clones a remote Git repository into an isolated, temporary sandbox directory with size verification, file filtering, and shallow/sparse checkout.",
)
async def clone_repository(request: RepoCloneRequest):
    result = await git_cloner_service.clone_repository(request)
    return result


@router.get(
    "/{repo_id}/scan",
    response_model=RepoScanResponse,
    summary="Scan Sandboxed Repository",
    description="Applies file filter guards to inventory all eligible source code files and line counts.",
)
async def scan_repository(repo_id: str):
    sandbox_path = sandbox_manager.get_sandbox_path(repo_id)
    if not sandbox_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox for repository {repo_id} not found.",
        )

    summary = file_filter_service.scan_repository(sandbox_path)
    file_metadata = [
        RepoFileMetadata(
            relative_path=f.relative_path,
            extension=f.extension,
            size_bytes=f.size_bytes,
            line_count=f.line_count,
        )
        for f in summary.eligible_files
    ]

    return RepoScanResponse(
        repo_id=repo_id,
        total_scanned=summary.total_scanned,
        eligible_count=summary.eligible_count,
        skipped_count=summary.skipped_count,
        total_code_lines=summary.total_code_lines,
        eligible_files=file_metadata,
    )


@router.post(
    "/{repo_id}/audit-secrets",
    response_model=RepoSecretsAuditResponse,
    summary="Audit and Redact Repository Secrets",
    description="Scans source files for credentials (API keys, tokens, high-entropy secrets) and optionally redacts them in-place.",
)
async def audit_repository_secrets(
    repo_id: str,
    redact_in_place: bool = Query(
        False, description="When true, rewrites source files to mask detected credentials with [REDACTED_SECRET:<type>]"
    ),
):
    sandbox_path = sandbox_manager.get_sandbox_path(repo_id)
    if not sandbox_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox for repository {repo_id} not found.",
        )

    scan_summary = file_filter_service.scan_repository(sandbox_path)
    all_findings: List[SecretFindingAudit] = []
    files_with_secrets_count = 0

    for file_info in scan_summary.eligible_files:
        fp = Path(file_info.absolute_path)
        sanitized_res = secrets_sanitizer_service.sanitize_file(fp, in_place=redact_in_place)

        if sanitized_res.findings_count > 0:
            files_with_secrets_count += 1
            for finding in sanitized_res.findings:
                all_findings.append(
                    SecretFindingAudit(
                        file_path=file_info.relative_path,
                        secret_type=finding.secret_type,
                        line_number=finding.line_number,
                        masked_preview=finding.masked_preview,
                    )
                )

    return RepoSecretsAuditResponse(
        repo_id=repo_id,
        total_secrets_found=len(all_findings),
        total_files_with_secrets=files_with_secrets_count,
        sanitized=redact_in_place,
        findings=all_findings,
    )


@router.post(
    "/{repo_id}/index",
    response_model=RepoIndexResponse,
    summary="Index Repository for Vector Search & RAG",
    description="Parses repository with language-aware AST, splits into semantic chunks, generates embeddings, and indexes in MongoDB Atlas & BM25.",
)
async def index_repository(repo_id: str):
    start_time = time.time()
    sandbox_path = sandbox_manager.get_sandbox_path(repo_id)
    if not sandbox_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox for repository {repo_id} not found.",
        )

    # 1. Filter clean source files
    scan_summary = file_filter_service.scan_repository(sandbox_path)

    # 2. Read contents of eligible files
    file_map = {}
    for f in scan_summary.eligible_files:
        try:
            content = Path(f.absolute_path).read_text(encoding="utf-8", errors="replace")
            file_map[f.relative_path] = content
        except Exception:
            continue

    # 3. Semantic AST Chunking
    chunk_summary = semantic_chunker_service.chunk_repository(repo_id, file_map)

    # 4. Batched OpenAI Embeddings
    embedding_result = await embedding_service.embed_chunks(chunk_summary.chunks)

    # 5. Store in MongoDB Vector Store
    await vector_store_service.index_chunks(
        repo_id, chunk_summary.chunks, embedding_result.vectors
    )

    # 6. Register BM25 sparse index
    hybrid_retriever_service.register_repo_chunks(repo_id, chunk_summary.chunks)

    duration = round(time.time() - start_time, 2)

    return RepoIndexResponse(
        repo_id=repo_id,
        status="indexed",
        files_indexed=len(file_map),
        chunks_created=chunk_summary.total_chunks,
        total_tokens=chunk_summary.total_tokens,
        cost_estimate_usd=embedding_result.cost_estimate_usd,
        duration_seconds=duration,
    )


@router.post(
    "/{repo_id}/search",
    response_model=HybridSearchResponse,
    summary="Hybrid Search Codebase",
    description="Queries indexed repository using combined BM25 keyword matching and dense vector retrieval.",
)
async def search_repository(
    repo_id: str,
    query: str = Query(..., description="Developer natural language question or code identifier"),
    top_k: int = Query(5, ge=1, le=20),
    alpha: float = Query(0.5, ge=0.0, le=1.0),
    file_path_filter: Optional[str] = Query(None),
):
    search_query = HybridSearchQuery(
        repo_id=repo_id,
        query=query,
        top_k=top_k,
        alpha=alpha,
        file_path_filter=file_path_filter,
    )
    return await hybrid_retriever_service.search(search_query)


@router.delete(
    "/{repo_id}/sandbox",
    response_model=SandboxCleanupResponse,
    summary="Cleanup Ephemeral Sandbox",
    description="Purges the temporary repository directory from disk to free resources.",
)
async def cleanup_sandbox(repo_id: str):
    success = sandbox_manager.cleanup_sandbox(repo_id)
    return SandboxCleanupResponse(
        repo_id=repo_id,
        success=success,
        message="Sandbox directory purged successfully" if success else "Directory not found",
    )
