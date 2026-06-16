import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- OpenAI Client ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Models ---
CHAT_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"

# --- RAG Settings ---
CHUNK_SIZE = 400
CHUNK_OVERLAP = 60
TOP_K_CHUNKS = 4
RECENCY_WEIGHT = 0.15

# --- Memory ---
MAX_HISTORY_TURNS = 10

# --- Fallback ---
SUPPORT_CONTACT = "support@moe-eservice.gov.sg"

# --- Internal Auth ---
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "dev-secret-key")

# --- Database ---
DB_CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=.;"
    "UID=sa;"
    "PWD=12345;"
    "DATABASE=moe_ai_prototype;"
    # "Integrated Security=SSPI;"
    "TrustServerCertificate=yes;"
)