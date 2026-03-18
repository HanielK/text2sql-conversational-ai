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
# Internal tables to exclude from schema retrieval
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
# Generate OpenAI embedding
# ---------------------------------------------------------

def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


# ---------------------------------------------------------
# Fetch database schema from Postgres
# ---------------------------------------------------------

def fetch_schema():
    schema_data = {}

    with get_connection() as conn:  # ✅ FIXED
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )

            tables = cur.fetchall()

            for table_row in tables:
                table = table_row[0]

                if table in EXCLUDED_TABLES:
                    continue

                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (table,)
                )

                columns = cur.fetchall()
                schema_data[table] = columns

    return schema_data


# ---------------------------------------------------------
# Convert schema into text descriptions
# ---------------------------------------------------------

def build_schema_descriptions(schema):
    descriptions = {}

    for table, columns in schema.items():
        column_text = "\n".join(
            f"{col[0]} ({col[1]})"
            for col in columns
        )

        description = f"""
Table {table}

Columns:
{column_text}
""".strip()

        descriptions[table] = description

    return descriptions


# ---------------------------------------------------------
# Store schema embeddings into pgvector table
# ---------------------------------------------------------

def store_schema_embeddings(descriptions):
    with get_connection() as conn:  # ✅ FIXED
        with conn.cursor() as cur:

            for table_name, schema_text in descriptions.items():
                print(f"Upserting schema for table: {table_name}")

                embedding = get_embedding(schema_text)

                cur.execute(
                    """
                    INSERT INTO schema_embeddings (table_name, schema_text, embedding)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (table_name)
                    DO UPDATE SET
                        schema_text = EXCLUDED.schema_text,
                        embedding = EXCLUDED.embedding
                    """,
                    (table_name, schema_text, embedding)
                )

        conn.commit()

    print("Schema embeddings indexed successfully")


# ---------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------

def index_database_schema():
    print("Fetching database schema...")

    schema = fetch_schema()

    print(f"Found {len(schema)} business tables")

    descriptions = build_schema_descriptions(schema)

    print("Generating embeddings...")

    store_schema_embeddings(descriptions)

    print("Schema indexing completed successfully")


# ---------------------------------------------------------

if __name__ == "__main__":
    index_database_schema()