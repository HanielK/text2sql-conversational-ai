import os
from backend.embeddings import get_embedding
from backend.db import get_connection
from pathlib import Path

DOCS_PATH = Path(__file__).resolve().parents[2] / "docs"

def ingest_docs():

    with get_connection() as conn:
        with conn.cursor() as cur:

            for file in os.listdir(DOCS_PATH):

                if not file.endswith(".txt"):
                    continue

                path = os.path.join(DOCS_PATH, file)

                with open(path, "r") as f:
                    content = f.read()

                embedding = get_embedding(content)

                cur.execute("""
                    INSERT INTO document_embeddings (document_name, content, embedding)
                    VALUES (%s, %s, %s)
                """, (file, content, embedding))

    print("✅ Document ingestion complete")


if __name__ == "__main__":
    ingest_docs()