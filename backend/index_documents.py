import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg
from openai import OpenAI

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

client = OpenAI(api_key=OPENAI_API_KEY)


def get_connection():
    return psycopg.connect(DATABASE_URL)


def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

    return chunks


def index_documents():
    docs_dir = Path(__file__).resolve().parents[1] / "docs"

    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs folder not found: {docs_dir}")

    files = list(docs_dir.glob("*.txt")) + list(docs_dir.glob("*.md"))

    if not files:
        print("No .txt or .md files found in docs/")
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
            for file_path in files:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                chunks = chunk_text(text)

                print(f"Indexing {file_path.name} with {len(chunks)} chunks")

                cur.execute(
                    "DELETE FROM document_embeddings WHERE source_file = %s",
                    (file_path.name,)
                )

                for idx, chunk in enumerate(chunks):
                    embedding = get_embedding(chunk)

                    cur.execute(
                        """
                        INSERT INTO document_embeddings
                        (source_file, chunk_index, chunk_text, embedding)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (file_path.name, idx, chunk, embedding)
                    )

            conn.commit()

    print("Document indexing completed successfully.")


if __name__ == "__main__":
    index_documents()