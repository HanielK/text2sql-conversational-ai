import os
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path

from backend.sql_generator import generate_sql
from backend.sql_validator import validate_sql
from backend.sql_executor import execute_sql

# Load .env from project root
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(title="AI SQL Copilot")


class QueryRequest(BaseModel):
    question: str


# -----------------------------------------------------
# Chart detection logic
# -----------------------------------------------------

def detect_chart(columns, rows):

    if not rows or len(columns) < 2:
        return None

    first_col = columns[0]
    second_col = columns[1]

    if isinstance(rows[0][1], (int, float)):
        return {
            "chart_type": "bar",
            "x": first_col,
            "y": second_col
        }

    return None


# -----------------------------------------------------
# Query endpoint
# -----------------------------------------------------

@app.post("/query")
def query_ai(payload: QueryRequest):

    question = payload.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    ai_result = generate_sql(question)

    sql = ai_result["sql"]
    reasoning = ai_result["reasoning"]
    tables_used = ai_result["tables_used"]

    is_valid, validation_message = validate_sql(sql)

    if not is_valid:
        raise HTTPException(status_code=400, detail=validation_message)

    execution = execute_sql(sql)

    if not execution["success"]:
        raise HTTPException(status_code=500, detail=execution["error"])

    chart = detect_chart(execution["columns"], execution["rows"])

    return {
        "question": question,
        "reasoning": reasoning,
        "tables_used": tables_used,
        "sql": sql,
        "columns": execution["columns"],
        "rows": execution["rows"],
        "chart": chart,
        "was_self_corrected": False
    }