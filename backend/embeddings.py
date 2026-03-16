import os
import psycopg
from openai import OpenAI
from dotenv import load_dotenv

# ---------------------------------------------------------
# Load environment variables from project root
# ---------------------------------------------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Debug verification
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

print("OpenAI key loaded:", OPENAI_API_KEY[:10] + "...")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


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
# Retrieve relevant schema from pgvector
# ---------------------------------------------------------

def retrieve_relevant_schema(question: str, top_k: int = 3):

    embedding = get_embedding(question)

    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()

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

    cur.close()
    conn.close()

    return rows