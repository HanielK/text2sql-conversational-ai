import os
import psycopg
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

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
    return psycopg.connect(DATABASE_URL, prepare_threshold=0)


def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def retrieve_relevant_docs(question: str, top_k: int = 5):
    embedding = get_embedding(question)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_file, chunk_index, chunk_text
                FROM document_embeddings
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                (embedding, top_k)
            )
            return cur.fetchall()


def answer_from_docs(question: str, top_k: int = 5):
    doc_rows = retrieve_relevant_docs(question, top_k=top_k)

    if not doc_rows:
        return {
            "reasoning": "No relevant document chunks were found.",
            "sources": [],
            "answer": "I could not find relevant document context."
        }

    doc_context = "\n\n".join(
        [
            f"[Source: {source_file} | Chunk: {chunk_index}]\n{chunk_text}"
            for source_file, chunk_index, chunk_text in doc_rows
        ]
    )

    prompt = f"""
You are an enterprise knowledge assistant.

Use ONLY the document context below to answer the question.

DOCUMENT CONTEXT:
{doc_context}

QUESTION:
{question}

Return a concise answer grounded in the provided document context.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    answer = response.choices[0].message.content.strip()

    return {
        "reasoning": "Answer generated from retrieved document chunks.",
        "sources": [row[0] for row in doc_rows],
        "answer": answer
    }