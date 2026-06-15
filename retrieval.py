import uuid
import math
from datetime import datetime, timezone
from dataclasses import dataclass

from config import client, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, TOP_K_CHUNKS, RECENCY_WEIGHT


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    embedding: list[float]
    uploaded_at: datetime
    source_label: str = ""


# In-memory store
_chunk_store: list[Chunk] = []


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap

    return chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def ingest_document(text: str, doc_id: str = None, source_label: str = "") -> dict:
    if doc_id is None:
        doc_id = str(uuid.uuid4())

    chunks_text = chunk_text(text)
    if not chunks_text:
        return {"doc_id": doc_id, "chunks_stored": 0}

    embeddings = embed_texts(chunks_text)
    uploaded_at = datetime.now(timezone.utc)

    for text_chunk, embedding in zip(chunks_text, embeddings):
        _chunk_store.append(Chunk(
            chunk_id=str(uuid.uuid4()),
            doc_id=doc_id,
            text=text_chunk,
            embedding=embedding,
            uploaded_at=uploaded_at,
            source_label=source_label,
        ))

    return {"doc_id": doc_id, "chunks_stored": len(chunks_text)}


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def recency_boost(uploaded_at: datetime, all_dates: list[datetime]) -> float:
    if not all_dates or len(set(all_dates)) == 1:
        return 0.0
    min_ts = min(all_dates).timestamp()
    max_ts = max(all_dates).timestamp()
    span = max_ts - min_ts
    if span == 0:
        return 0.0
    normalised = (uploaded_at.timestamp() - min_ts) / span
    return normalised * RECENCY_WEIGHT


def retrieve(query: str, top_k: int = TOP_K_CHUNKS) -> list[str]:
    if not _chunk_store:
        return []

    query_embedding = embed_query(query)
    all_dates = [c.uploaded_at for c in _chunk_store]

    scored = []
    for chunk in _chunk_store:
        score = (1 - RECENCY_WEIGHT) * cosine_similarity(query_embedding, chunk.embedding) + recency_boost(chunk.uploaded_at, all_dates)
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk.text for _, chunk in scored[:top_k]]


def get_store_stats() -> dict:
    return {
        "total_chunks": len(_chunk_store),
        "total_documents": len({c.doc_id for c in _chunk_store}),
    }