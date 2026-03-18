import os
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from backend.db import get_connection  # ✅ CENTRALIZED FIX

# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------
# Generate embedding (kept for future use)
# ---------------------------------------------------------

def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


# ---------------------------------------------------------
# 🔥 NEW: Dynamic schema retrieval (PRODUCTION-READY)
# ---------------------------------------------------------

def retrieve_relevant_schema(question: str, top_k: int = 3):
    """
    Dynamically pulls schema from Supabase (Postgres)
    Ignores embeddings for now to guarantee correctness
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """)
            rows = cur.fetchall()

    schema = {}

    for table, column, dtype in rows:
        schema.setdefault(table, []).append(f"{column} ({dtype})")

    schema_text = "\nDATABASE SCHEMA:\n"

    for table, columns in schema.items():
        schema_text += f"\nTable: {table}\n"
        for col in columns:
            schema_text += f"  - {col}\n"

    return schema_text


# ---------------------------------------------------------
# 🔥 TEMP: Disable column embeddings (simplifies debugging)
# ---------------------------------------------------------

def retrieve_relevant_columns(question: str, top_k: int = 8):
    return ""

