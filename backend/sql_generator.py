import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from backend.embeddings import retrieve_relevant_schema

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


def _build_prompt(question: str, schema_text: str, error_message: str | None = None):
    correction_block = ""
    if error_message:
        correction_block = f"""
PREVIOUS SQL EXECUTION ERROR:
{error_message}

Please correct the SQL using this error.
"""

    return f"""
You are an expert PostgreSQL data analyst.

DATABASE SCHEMA:
{schema_text}

USER QUESTION:
{question}

{correction_block}

Return your answer in valid JSON with this exact structure:

{{
  "reasoning": "why you selected these tables and logic",
  "tables_used": ["table1", "table2"],
  "sql": "valid PostgreSQL SQL"
}}

Rules:
- Return only JSON
- SQL must be valid PostgreSQL
- Use only tables from the schema
- Do not include markdown
- Prefer explicit column names
- Add LIMIT 1000 unless aggregation returns one row
"""


def generate_sql(question: str, error_message: str | None = None):
    schema_context = retrieve_relevant_schema(question)
    schema_text = "\n".join([row[1] for row in schema_context])

    prompt = _build_prompt(question, schema_text, error_message)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    try:
        result = json.loads(content)
    except Exception:
        result = {
            "reasoning": "Fallback parse used because model did not return clean JSON.",
            "tables_used": [row[0] for row in schema_context],
            "sql": content
        }

    result["schema_context"] = schema_context
    return result