import uuid
import json
import math
from datetime import datetime, timezone
from dataclasses import dataclass
import pyodbc
import hashlib
from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, TOP_K_CHUNKS, RECENCY_WEIGHT, DB_CONNECTION_STRING

# ---------------------------------------------------------------------------
# Local Embedding Model
# ---------------------------------------------------------------------------
_embedding_model = SentenceTransformer(EMBEDDING_MODEL)

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


# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

def get_connection():
    return pyodbc.connect(DB_CONNECTION_STRING)


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
    embeddings = _embedding_model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def ingest_document(text: str, doc_id: str = None, source_label: str = "") -> dict:
    # generate content hash
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # check if identical document already exists
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chunks WHERE content_hash = ?", content_hash)
    count = cursor.fetchone()[0]
    conn.close()

    if count > 0:
        return {"doc_id": "duplicate", "chunks_stored": 0, "skipped": True}
    
    if doc_id is None:
        doc_id = str(uuid.uuid4())

    chunks_text = chunk_text(text)
    if not chunks_text:
        return {"doc_id": doc_id, "chunks_stored": 0}

    embeddings = embed_texts(chunks_text)
    # uploaded_at = datetime.now(timezone.utc)
    uploaded_at = datetime.now(timezone.utc).replace(tzinfo=None)

    conn = get_connection()
    cursor = conn.cursor()

    for text_chunk, embedding in zip(chunks_text, embeddings):
        cursor.execute(
            """
            INSERT INTO chunks (chunk_id, doc_id, source_label, text, embedding, uploaded_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            str(uuid.uuid4()),
            doc_id,
            source_label,
            text_chunk,
            json.dumps(embedding),
            uploaded_at,
            content_hash,
        )

    conn.commit()
    conn.close()

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
    return (uploaded_at.timestamp() - min_ts) / span


def retrieve(query: str, top_k: int = TOP_K_CHUNKS) -> list[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT chunk_id, text, embedding, CAST(uploaded_at AS DATETIME2) AS uploaded_at FROM chunks")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    query_embedding = embed_query(query)
    all_dates = [row.uploaded_at for row in rows]

    scored = []
    for row in rows:
        embedding = json.loads(row.embedding)
        score = (1 - RECENCY_WEIGHT) * cosine_similarity(query_embedding, embedding) + RECENCY_WEIGHT * recency_boost(row.uploaded_at, all_dates)
        scored.append((score, row.text))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:top_k]]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_store_stats() -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chunks")
    total_chunks = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT doc_id) FROM chunks")
    total_documents = cursor.fetchone()[0]
    conn.close()
    return {
        "total_chunks": total_chunks,
        "total_documents": total_documents,
    }