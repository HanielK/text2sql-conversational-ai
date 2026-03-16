import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from backend.embeddings import retrieve_relevant_schema, retrieve_relevant_columns
from backend.context_memory import get_last_result

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
# Query planning step
# ---------------------------------------------------------

def plan_query(question: str, schema_text: str):

    prompt = f"""
You are a senior data analyst planning a SQL query.

DATABASE SCHEMA:
{schema_text}

USER QUESTION:
{question}

Return a JSON plan with this structure:

{{
  "tables_needed": ["table1", "table2"],
  "columns_needed": ["column1", "column2"],
  "filters": ["any filtering logic"],
  "aggregations": ["aggregation if needed"],
  "joins": ["join relationships if needed"]
}}

Rules:
- Only reference tables in the schema
- Do not write SQL
- Only return JSON
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except Exception:
        return {
            "tables_needed": [],
            "columns_needed": [],
            "filters": [],
            "aggregations": [],
            "joins": []
        }


# ---------------------------------------------------------
# SQL generation step
# ---------------------------------------------------------

def generate_sql_from_plan(
    question: str,
    schema_text: str,
    column_context: str,
    plan: dict,
    error_message: str | None,
    previous_result
):

    correction_block = ""
    if error_message:
        correction_block = f"""
PREVIOUS SQL EXECUTION ERROR:
{error_message}

Correct the SQL based on this error.
"""

    prompt = f"""
You are an expert PostgreSQL data analyst.

DATABASE SCHEMA:
{schema_text}

RELEVANT COLUMNS:
{column_context}

QUERY PLAN:
{json.dumps(plan, indent=2)}

PREVIOUS QUERY RESULT (if relevant):
{previous_result}

USER QUESTION:
{question}

{correction_block}

Return your answer in valid JSON with this structure:

{{
  "reasoning": "explain how the plan was converted into SQL",
  "tables_used": ["table1", "table2"],
  "sql": "valid PostgreSQL SQL"
}}

Rules:
- Return only JSON
- SQL must be valid PostgreSQL
- Use only tables from the schema
- Prefer explicit column names
- Add LIMIT 1000 unless aggregation returns one row
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except Exception:
        return {
            "reasoning": "Fallback parse used because model did not return clean JSON.",
            "tables_used": plan.get("tables_needed", []),
            "sql": content
        }


# ---------------------------------------------------------
# Main SQL generator
# ---------------------------------------------------------

def generate_sql(question: str, session_id: str | None = None, error_message: str | None = None):

    # -----------------------------------------------------
    # Retrieve relevant schema using embeddings
    # -----------------------------------------------------

    schema_context = retrieve_relevant_schema(question)
    schema_text = "\n".join([row[1] for row in schema_context])

    # -----------------------------------------------------
    # Retrieve relevant columns using embeddings
    # -----------------------------------------------------

    relevant_columns = retrieve_relevant_columns(question)

    column_context = "\n".join(
        [f"{row[0]}.{row[1]}" for row in relevant_columns]
    )

    # -----------------------------------------------------
    # Retrieve previous query result for context memory
    # -----------------------------------------------------

    previous_result = None

    if session_id:
        previous_result = get_last_result(session_id)

    # -----------------------------------------------------
    # Step 1: Plan the query
    # -----------------------------------------------------

    plan = plan_query(question, schema_text)

    # -----------------------------------------------------
    # Step 2: Generate SQL using the plan
    # -----------------------------------------------------

    result = generate_sql_from_plan(
        question,
        schema_text,
        column_context,
        plan,
        error_message,
        previous_result
    )

    result["schema_context"] = schema_context
    result["column_context"] = column_context
    result["query_plan"] = plan
    result["previous_result_used"] = previous_result is not None

    return result