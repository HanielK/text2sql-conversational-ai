import os
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from backend.db import get_connection  # ✅ FIXED

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
# Internal tables to exclude
# ---------------------------------------------------------

EXCLUDED_TABLES = {
    "schema_embeddings",
    "column_embeddings",
    "document_embeddings",
    "query_logs",
    "evaluation_metrics",
    "schema_vectors",
    "column_vectors",
}

# ---------------------------------------------------------
# Generate embedding
# ---------------------------------------------------------

def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


# ---------------------------------------------------------
# Fetch schema columns
# ---------------------------------------------------------

def fetch_columns():
    with get_connection() as conn:  # ✅ FIXED
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
                """
            )

            rows = cur.fetchall()

    # filter out system tables
    return [
        row for row in rows
        if row[0] not in EXCLUDED_TABLES
    ]


# ---------------------------------------------------------
# Index columns (UPSERT SAFE)
# ---------------------------------------------------------

def index_columns():
    columns = fetch_columns()

    print(f"Found {len(columns)} business columns")

    with get_connection() as conn:  # ✅ FIXED
        with conn.cursor() as cur:

            for table_name, column_name, dtype in columns:

                print(f"Upserting column: {table_name}.{column_name}")

                description = f"""
Table: {table_name}
Column: {column_name}
Data type: {dtype}
""".strip()

                embedding = get_embedding(description)

                cur.execute(
                    """
                    INSERT INTO column_embeddings
                    (table_name, column_name, column_description, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (table_name, column_name)
                    DO UPDATE SET
                        column_description = EXCLUDED.column_description,
                        embedding = EXCLUDED.embedding
                    """,
                    (table_name, column_name, description, embedding)
                )

        conn.commit()

    print("Column embeddings indexed successfully")


# ---------------------------------------------------------

if __name__ == "__main__":
    index_columns()