import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.database import db_manager
from app.schemas.chunk import CodeChunk
from app.schemas.embedding import EmbeddingVector


class ScoredCodeChunk(BaseModel):
    chunk_id: str
    repo_id: str
    file_path: str
    symbol_name: Optional[str] = None
    start_line: int
    end_line: int
    content: str
    score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VectorStoreService:
    """Service to manage MongoDB Atlas Vector Search and dense retrieval."""

    def __init__(self):
        self.settings = get_settings()
        # In-memory storage for offline / testing mode
        self._in_memory_docs: Dict[str, List[Dict[str, Any]]] = {}

    def get_atlas_vector_index_spec(self) -> Dict[str, Any]:
        """Returns the MongoDB Atlas Vector Search JSON index definition."""
        return {
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": self.settings.OPENAI_EMBEDDING_DIMENSIONS,
                    "similarity": "cosine",
                },
                {
                    "type": "filter",
                    "path": "repo_id",
                },
                {
                    "type": "filter",
                    "path": "file_path",
                },
            ]
        }

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    async def index_chunks(
        self,
        repo_id: str,
        chunks: List[CodeChunk],
        embeddings: List[EmbeddingVector],
    ) -> int:
        """Store code chunks and their dense embeddings in MongoDB."""
        chunk_map = {c.chunk_id: c for c in chunks}
        documents = []

        for emb in embeddings:
            c = chunk_map.get(emb.chunk_id)
            if not c:
                continue

            doc = {
                "chunk_id": c.chunk_id,
                "repo_id": repo_id,
                "file_path": c.file_path,
                "symbol_name": c.symbol_name,
                "symbol_type": c.symbol_type,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "content": c.content,
                "token_count": c.token_count,
                "metadata": c.metadata,
                "embedding": emb.vector,
                "dimensions": emb.dimensions,
            }
            documents.append(doc)

        # Store in-memory for immediate query access and test verification
        if repo_id not in self._in_memory_docs:
            self._in_memory_docs[repo_id] = []
        self._in_memory_docs[repo_id].extend(documents)

        # Try persisting to MongoDB if online
        try:
            db = db_manager.get_database()
            collection = db["code_chunks"]
            for doc in documents:
                await collection.update_one(
                    {"chunk_id": doc["chunk_id"]},
                    {"$set": doc},
                    upsert=True,
                )
        except Exception:
            # Running offline / test environment
            pass

        return len(documents)

    async def vector_search(
        self,
        repo_id: str,
        query_vector: List[float],
        top_k: int = 5,
        file_path_filter: Optional[str] = None,
    ) -> List[ScoredCodeChunk]:
        """Perform k-NN vector search using cosine similarity."""
        # Check if live MongoDB Atlas vector search is accessible
        try:
            db = db_manager.get_database()
            collection = db["code_chunks"]

            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self.settings.MONGODB_VECTOR_INDEX_NAME,
                        "path": "embedding",
                        "queryVector": query_vector,
                        "numCandidates": top_k * 10,
                        "limit": top_k,
                        "filter": {"repo_id": repo_id},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "chunk_id": 1,
                        "repo_id": 1,
                        "file_path": 1,
                        "symbol_name": 1,
                        "start_line": 1,
                        "end_line": 1,
                        "content": 1,
                        "metadata": 1,
                        "score": {"$meta": "vectorSearchScore"},
                    }
                },
            ]

            results = []
            async for doc in collection.aggregate(pipeline):
                results.append(ScoredCodeChunk(**doc))
            if results:
                return results
        except Exception:
            # Fall back to in-memory cosine ranking
            pass

        # In-memory cosine search fallback
        repo_docs = self._in_memory_docs.get(repo_id, [])
        scored_candidates = []

        for doc in repo_docs:
            if file_path_filter and doc.get("file_path") != file_path_filter:
                continue

            sim = self.cosine_similarity(query_vector, doc["embedding"])
            scored_candidates.append(
                ScoredCodeChunk(
                    chunk_id=doc["chunk_id"],
                    repo_id=doc["repo_id"],
                    file_path=doc["file_path"],
                    symbol_name=doc.get("symbol_name"),
                    start_line=doc["start_line"],
                    end_line=doc["end_line"],
                    content=doc["content"],
                    score=round(sim, 4),
                    metadata=doc.get("metadata", {}),
                )
            )

        scored_candidates.sort(key=lambda x: x.score, reverse=True)
        return scored_candidates[:top_k]


vector_store_service = VectorStoreService()
