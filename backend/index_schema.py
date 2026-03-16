import os
import psycopg
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

client = OpenAI(api_key=OPENAI_API_KEY)


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

    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
    """)

    tables = cur.fetchall()

    schema_data = {}

    for table_row in tables:

        table = table_row[0]

        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table,))

        columns = cur.fetchall()

        schema_data[table] = columns

    cur.close()
    conn.close()

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
"""

        descriptions[table] = description.strip()

    return descriptions


# ---------------------------------------------------------
# Store schema embeddings into pgvector table
# ---------------------------------------------------------

def store_schema_embeddings(descriptions):

    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()

    for table, description in descriptions.items():

        print(f"Embedding schema for table: {table}")

        embedding = get_embedding(description)

        cur.execute(
            """
            INSERT INTO schema_embeddings (table_name, schema_text, embedding)
            VALUES (%s, %s, %s)
            ON CONFLICT (table_name)
            DO UPDATE SET
                schema_text = EXCLUDED.schema_text,
                embedding = EXCLUDED.embedding
            """,
            (table, description, embedding)
        )

    conn.commit()
    cur.close()
    conn.close()


# ---------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------

def index_database_schema():

    print("Fetching database schema...")

    schema = fetch_schema()

    print(f"Found {len(schema)} tables")

    descriptions = build_schema_descriptions(schema)

    print("Generating embeddings...")

    store_schema_embeddings(descriptions)

    print("Schema indexing completed successfully")


# ---------------------------------------------------------

if __name__ == "__main__":
    index_database_schema()