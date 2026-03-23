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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------
# DB Connection
# ---------------------------------------------------------

def get_connection():
    return psycopg.connect(
        DATABASE_URL,
        autocommit=True,
        prepare_threshold=None  # 🔥 DISABLE prepared statements (REQUIRED for Supabase)
    )


# ---------------------------------------------------------
# Embedding
# ---------------------------------------------------------

def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


# ---------------------------------------------------------
# Retrieve relevant documents (FIXED)
# ---------------------------------------------------------

def retrieve_relevant_docs(question: str, top_k: int = 3):
    embedding = get_embedding(question)

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT document_name, content
                FROM document_embeddings
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                (embedding, top_k)
            )

            rows = cur.fetchall()

    return rows


# ---------------------------------------------------------
# Answer from documents (FIXED + IMPROVED)
# ---------------------------------------------------------

def answer_from_docs(question: str, top_k: int = 5):
    doc_rows = retrieve_relevant_docs(question, top_k=top_k)

    if not doc_rows:
        return {
            "reasoning": "No relevant documents found.",
            "sources": [],
            "answer": "I could not find relevant document context."
        }

    # -----------------------------------------------------
    # Build document context (FIXED for your schema)
    # Add LIMIT 1000 characters to content length to avoid token bloat
    # -----------------------------------------------------
    doc_context = "\n\n".join(
        [
            f"[Source: {document_name}]\n{content[:1000]}"
            for document_name, content in doc_rows
        ]
    )

    # -----------------------------------------------------
    # Prompt
    # -----------------------------------------------------
    prompt = f"""
You are an enterprise knowledge assistant.

Use ONLY the document context below to answer the question.
If the answer is not in the context, say you don't know.

DOCUMENT CONTEXT:
{doc_context}

QUESTION:
{question}

Return a concise, accurate answer grounded in the document context.
"""

    # -----------------------------------------------------
    # LLM call
    # -----------------------------------------------------
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    answer = response.choices[0].message.content.strip()

    # -----------------------------------------------------
    # Return structured response
    # -----------------------------------------------------
    return {
        "reasoning": "Answer generated from retrieved documents.",
        "sources": [row[0] for row in doc_rows],  # document_name
        "answer": answer
    }