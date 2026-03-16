import os
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path

from backend.sql_generator import generate_sql
from backend.sql_validator import validate_sql
from backend.sql_executor import execute_sql

# -----------------------------------------------------
# Load environment variables from project root
# -----------------------------------------------------

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

app = FastAPI(title="AI SQL Copilot")


# -----------------------------------------------------
# Request model
# -----------------------------------------------------


class QueryRequest(BaseModel):
    question: str
    session_id: str


# -----------------------------------------------------
# Chart detection logic
# -----------------------------------------------------


def detect_chart(columns, rows):

    if not rows or len(columns) < 2:
        return None

    first_col = columns[0]
    second_col = columns[1]

    if isinstance(rows[0][1], (int, float)):
        return {"chart_type": "bar", "x": first_col, "y": second_col}

    return None


# -----------------------------------------------------
# Query endpoint
# -----------------------------------------------------


@app.post("/query")
def query_ai(payload: QueryRequest):

    question = payload.question.strip()
    session_id = payload.session_id

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # -------------------------------------------------
    # Generate SQL using AI
    # -------------------------------------------------

    ai_result = generate_sql(question, session_id)

    sql = ai_result["sql"]
    reasoning = ai_result["reasoning"]
    tables_used = ai_result["tables_used"]

    # -------------------------------------------------
    # Validate SQL
    # -------------------------------------------------

    is_valid, validation_message = validate_sql(sql)

    if not is_valid:
        raise HTTPException(status_code=400, detail=validation_message)

    # -------------------------------------------------
    # Execute SQL
    # -------------------------------------------------

    execution = execute_sql(sql)

    if not execution["success"]:
        raise HTTPException(status_code=500, detail=execution["error"])


    # -------------------------------------------------
    # Log query for conversation memory + result context
    # -------------------------------------------------

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                result_payload = {
                    "columns": execution["columns"],
                    "rows": execution["rows"][:50],
                }

                cur.execute(
                    """
                    INSERT INTO query_logs
                    (session_id, question, generated_sql, execution_time, success, result_json)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        question,
                        sql,
                        execution.get("execution_time", 0),
                        execution["success"],
                        psycopg.types.json.Jsonb(result_payload),
                    ),
                )

                conn.commit()

    except Exception as e:
        print("Query logging failed:", str(e))


    # -------------------------------------------------
    # Detect chart opportunity
    # -------------------------------------------------

    chart = detect_chart(execution["columns"], execution["rows"])


    return {
        "question": question,
        "reasoning": reasoning,
        "tables_used": tables_used,
        "sql": sql,
        "columns": execution["columns"],
        "rows": execution["rows"],
        "chart": chart,
        "was_self_corrected": False,
    }
