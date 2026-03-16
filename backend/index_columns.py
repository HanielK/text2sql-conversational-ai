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

client = OpenAI(api_key=OPENAI_API_KEY)


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

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
            """)

            return cur.fetchall()


# ---------------------------------------------------------
# Index columns
# ---------------------------------------------------------

def index_columns():

    columns = fetch_columns()

    print(f"Found {len(columns)} columns")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            for table, column, dtype in columns:

                description = f"""
Table {table}
Column {column}
Data type {dtype}
"""

                embedding = get_embedding(description)

                cur.execute(
                    """
                    INSERT INTO column_embeddings
                    (table_name, column_name, column_description, embedding)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (table, column, description, embedding)
                )

            conn.commit()

    print("Column embeddings indexed successfully")


# ---------------------------------------------------------

if __name__ == "__main__":
    index_columns()