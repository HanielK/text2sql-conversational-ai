import os
import psycopg
from dotenv import load_dotenv
from openai import OpenAI

print("Starting schema ingestion...")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

conn = psycopg.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

cur.execute("""
CREATE TABLE IF NOT EXISTS schema_embeddings (
    id SERIAL PRIMARY KEY,
    table_name TEXT,
    schema_text TEXT,
    embedding vector(1536)
);
""")

# refresh existing schema knowledge base
cur.execute("DELETE FROM schema_embeddings;")
conn.commit()

print("Reading database schema...")

cur.execute("""
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position
""")

rows = cur.fetchall()

schema_map = {}

for table, column, dtype in rows:
    if table not in schema_map:
        schema_map[table] = []
    schema_map[table].append(f"{column} ({dtype})")

print("Generating embeddings...")

for table, columns in schema_map.items():
    schema_text = f"Table: {table}\nColumns: {', '.join(columns)}"

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=schema_text
    )

    embedding = response.data[0].embedding

    cur.execute("""
        INSERT INTO schema_embeddings (table_name, schema_text, embedding)
        VALUES (%s, %s, %s)
    """, (table, schema_text, embedding))

conn.commit()

print("Schema ingestion complete!")

cur.close()
conn.close()