from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware

from config import client, CHAT_MODEL
from models import FAQRequest, FAQResponse, HealthResponse, UploadRequest, UploadResponse
from assistants.faq import handle_faq
# from retrieval import ingest_document, get_store_stats
from retrieval_sql import ingest_document, get_store_stats

from fastapi import UploadFile, File
from document_processor import extract_text_from_pdf

app = FastAPI(
    title="MOE e-Service AI Prototype",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check():
    try:
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": "Reply with the word OK only."}],
            max_tokens=5,
        )
        connected = "ok" in response.choices[0].message.content.strip().lower()
    except Exception as e:
        print(f"[health] OpenAI connection failed: {e}")
        connected = False

    stats = get_store_stats()
    return HealthResponse(
        status="ok" if connected else "degraded",
        openai_connected=connected,
        model=CHAT_MODEL,
        total_chunks=stats["total_chunks"],
        total_documents=stats["total_documents"],
    )


# ---------------------------------------------------------------------------
# Document ingestion
# ---------------------------------------------------------------------------

@app.post("/ai/documents/ingest", response_model=UploadResponse)
async def ingest_doc(req: UploadRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty document text")

    result = ingest_document(text=req.text, source_label=req.source_label)
    return UploadResponse(
        doc_id=result["doc_id"],
        chunks_stored=result["chunks_stored"],
        message=f"Ingested {result['chunks_stored']} chunks from '{req.source_label or 'unnamed document'}'",
    )

# ---------------------------------------------------------------------------
# Chunk inspection (for testing)
# ---------------------------------------------------------------------------
# @app.get("/ai/documents/chunks") # for using in-memory store
# async def get_chunks():
#     from retrieval import _chunk_store
#     return [
#         {
#             "chunk_id": c.chunk_id,
#             "doc_id": c.doc_id,
#             "source_label": c.source_label,
#             "uploaded_at": c.uploaded_at.isoformat(),
#             "text": c.text,
#         }
#         for c in _chunk_store
#     ]

@app.get("/ai/documents/chunks") # for using SQL database
async def get_chunks():
    from retrieval_sql import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT chunk_id, doc_id, source_label, uploaded_at, text FROM chunks")
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "chunk_id": row.chunk_id,
            "doc_id": row.doc_id,
            "source_label": row.source_label,
            "uploaded_at": row.uploaded_at.isoformat(),
            "text": row.text,
        }
        for row in rows
    ]



# ---------------------------------------------------------------------------
# Chunk stats (for testing)
# ---------------------------------------------------------------------------
@app.get("/ai/documents/stats")
async def get_stats():
    return get_store_stats()

# ---------------------------------------------------------------------------
# FAQ Assistant
# ---------------------------------------------------------------------------

@app.post("/ai/faq/chat", response_model=FAQResponse)
async def faq_chat(req: FAQRequest):
    try:
        return handle_faq(req)
    except Exception as e:
        print(f"[faq] Error for user {req.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal AI error")

# ---------------------------------------------------------------------------
# Document processor (for testing)
# ---------------------------------------------------------------------------

# @app.post("/ai/documents/upload", response_model=UploadResponse)
# async def upload_doc(file: UploadFile = File(...)):
#     if not file.filename.endswith(".pdf"):
#         raise HTTPException(status_code=400, detail="Only PDF files are supported for now")

#     contents = await file.read()
#     text = extract_text_from_pdf(contents)

#     if not text.strip():
#         raise HTTPException(status_code=400, detail="Could not extract text from PDF")

#     result = ingest_document(text=text, source_label=file.filename)
#     return UploadResponse(
#         doc_id=result["doc_id"],
#         chunks_stored=result["chunks_stored"],
#         message=f"Ingested {result['chunks_stored']} chunks from '{file.filename}'",
#     )

@app.post("/ai/documents/upload", response_model=UploadResponse)
async def upload_doc(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for now")

    contents = await file.read()
    text = extract_text_from_pdf(contents)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

    result = ingest_document(text=text, source_label=file.filename)

    if result.get("skipped"):
        return UploadResponse(
            doc_id="duplicate",
            chunks_stored=0,
            message=f"'{file.filename}' already exists in the knowledge base — skipped.",
        )

    return UploadResponse(
        doc_id=result["doc_id"],
        chunks_stored=result["chunks_stored"],
        message=f"Ingested {result['chunks_stored']} chunks from '{file.filename}'",
    )

# ---------------------------------------------------------------------------
# Dev runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)