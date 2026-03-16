import os
import psycopg
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# ---------------------------------------------------------
# Load environment variables from project root
# ---------------------------------------------------------

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

print("OpenAI key loaded:", OPENAI_API_KEY[:10] + "...")

# ---------------------------------------------------------
# Initialize OpenAI client
# ---------------------------------------------------------

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------
# Database connection helper
# ---------------------------------------------------------

def get_connection():
    return psycopg.connect(DATABASE_URL)


# ---------------------------------------------------------
# Generate embedding from OpenAI
# ---------------------------------------------------------

def get_embedding(text: str):

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )

    return response.data[0].embedding


# ---------------------------------------------------------
# Retrieve relevant tables from pgvector
# ---------------------------------------------------------

def retrieve_relevant_schema(question: str, top_k: int = 3):

    embedding = get_embedding(question)

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT table_name, schema_text
                FROM schema_embeddings
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                (embedding, top_k)
            )

            rows = cur.fetchall()

    return rows


# ---------------------------------------------------------
# Retrieve relevant columns from pgvector
# ---------------------------------------------------------

def retrieve_relevant_columns(question: str, top_k: int = 8):

    embedding = get_embedding(question)

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT table_name, column_name
                FROM column_embeddings
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                (embedding, top_k)
            )

            rows = cur.fetchall()

    return rows