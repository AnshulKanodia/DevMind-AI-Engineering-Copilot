import math
import re
from typing import Dict, List, Optional, Set
from collections import Counter

from app.schemas.chunk import CodeChunk
from app.schemas.retrieval import HybridSearchQuery, HybridSearchResponse, RetrievedChunk
from app.services.embedding_service import embedding_service
from app.services.vector_store import ScoredCodeChunk, vector_store_service


class BM25Scorer:
    """Lightweight in-memory BM25Okapi scorer tailored for code tokens."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_dl = 0.0
        self.doc_lens: List[int] = []
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Split text into code identifiers and lowercased tokens."""
        # Split on non-alphanumeric and also split camelCase
        raw_tokens = re.findall(r"[A-Za-z0-9]+", text)
        tokens = []
        for t in raw_tokens:
            tokens.append(t.lower())
            # Split camelCase: e.g. processPayment -> process, payment
            sub_tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", t)
            if len(sub_tokens) > 1:
                tokens.extend([st.lower() for st in sub_tokens])
        return tokens

    def fit(self, documents: List[str]):
        """Fit BM25 parameters across corpus."""
        self.corpus_size = len(documents)
        if self.corpus_size == 0:
            return

        self.doc_freqs = []
        self.doc_lens = []
        df: Counter = Counter()

        for doc in documents:
            tokens = self.tokenize(doc)
            self.doc_lens.append(len(tokens))
            freq = Counter(tokens)
            self.doc_freqs.append(freq)
            for token in freq.keys():
                df[token] += 1

        self.avg_dl = sum(self.doc_lens) / self.corpus_size

        # Compute IDF for all tokens
        for token, freq in df.items():
            # Standard Lucene/BM25 IDF formula
            self.idf[token] = math.log(
                (self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0
            )

    def score(self, query: str) -> List[float]:
        """Calculate BM25 scores for all corpus documents against query."""
        if self.corpus_size == 0:
            return []

        q_tokens = self.tokenize(query)
        scores = [0.0] * self.corpus_size

        for i in range(self.corpus_size):
            doc_len = self.doc_lens[i]
            freqs = self.doc_freqs[i]

            for q in q_tokens:
                if q not in freqs:
                    continue
                tf = freqs[q]
                idf = self.idf.get(q, 0.0)
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_dl or 1.0)))
                scores[i] += idf * (tf * (self.k1 + 1.0)) / denom

        return scores


class HybridRetrieverService:
    """Hybrid code search combining BM25 keyword matching with dense vector embeddings."""

    def __init__(self):
        # Keep BM25 scorers mapped by repo_id
        self._bm25_indices: Dict[str, BM25Scorer] = {}
        self._repo_chunks: Dict[str, List[CodeChunk]] = {}

    def register_repo_chunks(self, repo_id: str, chunks: List[CodeChunk]):
        """Build and cache BM25 sparse index for repository chunks."""
        self._repo_chunks[repo_id] = chunks
        scorer = BM25Scorer()
        scorer.fit([c.content for c in chunks])
        self._bm25_indices[repo_id] = scorer

    # Alias for indexing convenience
    index_corpus = register_repo_chunks

    async def search(self, params: HybridSearchQuery) -> HybridSearchResponse:
        """Execute hybrid search using alpha-weighted score fusion."""
        repo_id = params.repo_id
        chunks = self._repo_chunks.get(repo_id, [])

        # 1. Dense Vector Search
        query_vec = await embedding_service.embed_query(params.query)
        dense_results = await vector_store_service.vector_search(
            repo_id=repo_id,
            query_vector=query_vec,
            top_k=max(params.top_k * 2, 10),
            file_path_filter=params.file_path_filter,
        )
        dense_scores_by_id: Dict[str, float] = {r.chunk_id: r.score for r in dense_results}

        # 2. Sparse BM25 Keyword Search
        bm25_scorer = self._bm25_indices.get(repo_id)
        sparse_scores_by_id: Dict[str, float] = {}

        if bm25_scorer and chunks:
            bm25_scores = bm25_scorer.score(params.query)
            max_bm25 = max(bm25_scores) if bm25_scores and max(bm25_scores) > 0 else 1.0
            for c, raw_score in zip(chunks, bm25_scores):
                if params.file_path_filter and c.file_path != params.file_path_filter:
                    continue
                # Normalize BM25 score to [0, 1] range
                sparse_scores_by_id[c.chunk_id] = raw_score / max_bm25

        # 3. Alpha-Weighted Fusion & Ranking
        # Combined = alpha * dense + (1 - alpha) * sparse
        all_candidate_ids: Set[str] = set(dense_scores_by_id.keys()) | set(sparse_scores_by_id.keys())
        chunk_lookup: Dict[str, CodeChunk] = {c.chunk_id: c for c in chunks}

        # Fallback lookup if chunk was only in vector store
        for d in dense_results:
            if d.chunk_id not in chunk_lookup:
                chunk_lookup[d.chunk_id] = CodeChunk(
                    chunk_id=d.chunk_id,
                    repo_id=d.repo_id,
                    file_path=d.file_path,
                    symbol_name=d.symbol_name,
                    start_line=d.start_line,
                    end_line=d.end_line,
                    content=d.content,
                    token_count=10,
                    metadata=d.metadata,
                )

        ranked_results: List[RetrievedChunk] = []
        for cid in all_candidate_ids:
            chunk = chunk_lookup.get(cid)
            if not chunk:
                continue

            d_score = dense_scores_by_id.get(cid, 0.0)
            s_score = sparse_scores_by_id.get(cid, 0.0)
            combined = round(params.alpha * d_score + (1.0 - params.alpha) * s_score, 4)

            citation = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
            ranked_results.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    file_path=chunk.file_path,
                    symbol_name=chunk.symbol_name,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    combined_score=combined,
                    dense_score=round(d_score, 4),
                    sparse_score=round(s_score, 4),
                    citation_label=citation,
                    metadata=chunk.metadata,
                )
            )

        # Sort by combined score descending
        ranked_results.sort(key=lambda x: x.combined_score, reverse=True)
        top_results = ranked_results[: params.top_k]

        return HybridSearchResponse(
            repo_id=repo_id,
            query=params.query,
            total_results=len(top_results),
            chunks=top_results,
        )


hybrid_retriever_service = HybridRetrieverService()
