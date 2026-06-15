# MOE e-Service AI Prototype — Startup Guide

This is the AI prototype for the MOE e-Service portal. It provides two AI assistants:
- **FAQ Assistant** — answers general portal questions using a RAG pipeline
- **FAS Assistant** — guides users through the Financial Assistance Scheme form *(pending BA confirmation)*

The prototype is built with Python (FastAPI) and is designed to be called by the C# backend via HTTP.

---

## Prerequisites

Make sure you have the following installed before starting:

- Python 3.10 or above
- SQL Server Management Studio (SSMS) with a `(localdb)\MSSQLLocalDB` instance running
- ODBC Driver 17 or 18 for SQL Server
- An OpenAI API key

---

## First-Time Setup

### 1. Create the database

Open SSMS, connect to `(localdb)\MSSQLLocalDB`, and run the following:

```sql
CREATE DATABASE moe_ai_prototype;
GO

USE moe_ai_prototype;
GO

CREATE TABLE chunks (
    chunk_id NVARCHAR(36) PRIMARY KEY,
    doc_id NVARCHAR(36) NOT NULL,
    source_label NVARCHAR(255),
    text NVARCHAR(MAX) NOT NULL,
    embedding NVARCHAR(MAX) NOT NULL,
    uploaded_at DATETIMEOFFSET NOT NULL,
    content_hash NVARCHAR(64)
);
GO
```

### 2. Install dependencies

Open a terminal in the project folder and activate the virtual environment:

```powershell
cd ai_prototype
venv\Scripts\activate
```

Then install packages:

```powershell
pip install -r requirements.txt
```

### 3. Set your OpenAI API key

Run this in PowerShell before starting the server (required every new terminal session):

```powershell
$env:OPENAI_API_KEY="sk-..."
```

---

## Starting the Prototype

You need **two terminals** open — one for the API server, one for the Streamlit UI.

### Terminal 1 — API Server

```powershell
venv\Scripts\activate
$env:OPENAI_API_KEY="sk-..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`.

### Terminal 2 — Streamlit UI

```powershell
venv\Scripts\activate
streamlit run app.py
```

The chat interface will open automatically at `http://localhost:8501`.

---

## Using the Prototype

### Step 1 — Verify the connection

Check that the API server and OpenAI are connected:

```powershell
curl.exe http://localhost:8000/health
```

You should see `"openai_connected": true`.

### Step 2 — Upload documents

In the Streamlit UI, use the **Upload Documents** panel on the left sidebar to upload PDF documents. Click **Ingest Document** after selecting a file.

- Documents are stored persistently in SQL Server — you only need to upload once.
- Uploading the same file again will show a warning and skip re-ingestion.
- Uploading a revised version of a file (same name, different content) will ingest it as a new document.

### Step 3 — Chat

Type questions in the chat box. The assistant will:
- Answer questions about the portal using the uploaded documents
- Politely decline off-topic questions
- Fall back to a support contact if it cannot answer confidently

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Connection test — checks OpenAI and returns DB stats |
| POST | `/ai/faq/chat` | FAQ Assistant |
| POST | `/ai/documents/upload` | Upload a PDF into the knowledge base |
| POST | `/ai/documents/ingest` | Ingest raw text into the knowledge base |
| GET | `/ai/documents/stats` | Returns total chunks and documents in DB |
| GET | `/ai/documents/chunks` | Returns all stored chunks (for debugging) |
| GET | `/docs` | Swagger UI — interactive API documentation |

---

## Architecture Overview

```
User (Streamlit UI)
        │
        ▼
FastAPI Python Service (port 8000)
        │
        ├── Intent Detection (OpenAI)
        ├── RAG Retrieval (embeddings → SQL Server)
        └── Answer Generation (OpenAI)
                │
                ▼
        SQL Server (localdb)
        └── chunks table (text + embeddings)
```

**Key design decisions:**
- **Stateless service** — Python holds no session state. The frontend sends the last 10 messages with each request.
- **RAG pipeline** — documents are chunked at upload, embedded via OpenAI, and stored in SQL Server. Relevant chunks are retrieved per query and passed as context to the LLM.
- **One LLM call per request** — FAQ uses max 2 calls (intent detection + answer). FAS uses 1.
- **Duplicate detection** — documents are hashed on upload; identical content is skipped automatically.
- **Recency weighting** — newer documents are ranked slightly higher in retrieval.

---

## File Structure

```
ai_prototype/
├── main.py                  # FastAPI app and endpoint definitions
├── config.py                # OpenAI client, DB connection string, constants
├── models.py                # Request/response models (DTO contract with C#)
├── prompts.py               # All prompt templates
├── retrieval.py             # Original in-memory retrieval (reference)
├── retrieval_sql.py         # SQL Server retrieval (active)
├── document_processor.py   # PDF text extraction
├── app.py                   # Streamlit chat UI
├── assistants/
│   ├── faq.py               # FAQ Assistant logic
│   └── fas.py               # FAS Assistant logic (parked)
└── requirements.txt
```

---

## Known Limitations (Prototype)

- **PDF extraction quality** — heavily image-based PDFs may have incomplete text extraction. Text-based PDFs work well.
- **FAS Assistant** — parked pending BA confirmation from customer.
- **Document management** — deleting or replacing documents will be handled by C# in production. For now, clear the `chunks` table in SSMS if a full reset is needed:
  ```sql
  DELETE FROM chunks;
  ```
- **Language support** — English only for now. Multilingual support deferred.
- **Auth** — internal API key auth between C# and Python is scaffolded but not enforced in dev mode.

---

## Open Questions for BAs

- VICA requirement from GovTech — if mandated, OpenAI will need to be replaced.
- FAS Assistant scope — confirm whether AI guidance on form fields is still in scope.
- Language requirements — does the chatbot need to support Mandarin, Malay, or Tamil?
- Conversation history retention period — how long should chat history be stored?
- User ability to delete their own chat history.
