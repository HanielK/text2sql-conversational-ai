import os
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.sql_generator import generate_sql
from backend.sql_validator import validate_sql
from backend.sql_executor import execute_sql

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(title="Text-to-SQL AI Backend")


class QueryRequest(BaseModel):
    question: str


def log_query(question: str, reasoning: str, sql: str, success: bool, error_message: str | None):
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS query_history (
            id BIGSERIAL PRIMARY KEY,
            question TEXT,
            reasoning TEXT,
            generated_sql TEXT,
            success BOOLEAN,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        INSERT INTO query_history (question, reasoning, generated_sql, success, error_message)
        VALUES (%s, %s, %s, %s, %s)
    """, (question, reasoning, sql, success, error_message))

    conn.commit()
    cur.close()
    conn.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query")
def query_ai(payload: QueryRequest):
    question = payload.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # First attempt
    first_pass = generate_sql(question)
    sql = first_pass["sql"]
    reasoning = first_pass["reasoning"]
    tables_used = first_pass.get("tables_used", [])
    schema_context = first_pass.get("schema_context", [])

    is_valid, validation_message = validate_sql(sql)

    if not is_valid:
        log_query(question, reasoning, sql, False, validation_message)
        raise HTTPException(status_code=400, detail=validation_message)

    execution = execute_sql(sql)

    # Self-correction loop
    if not execution["success"]:
        retry_pass = generate_sql(question, error_message=execution["error"])
        retry_sql = retry_pass["sql"]
        retry_reasoning = retry_pass["reasoning"]
        retry_tables_used = retry_pass.get("tables_used", [])
        retry_schema_context = retry_pass.get("schema_context", [])

        is_valid_retry, validation_message_retry = validate_sql(retry_sql)

        if not is_valid_retry:
            log_query(question, retry_reasoning, retry_sql, False, validation_message_retry)
            raise HTTPException(status_code=400, detail=validation_message_retry)

        retry_execution = execute_sql(retry_sql)

        if not retry_execution["success"]:
            log_query(question, retry_reasoning, retry_sql, False, retry_execution["error"])
            raise HTTPException(status_code=500, detail=retry_execution["error"])

        log_query(question, retry_reasoning, retry_sql, True, None)

        return {
            "question": question,
            "reasoning": retry_reasoning,
            "tables_used": retry_tables_used,
            "schema_context": retry_schema_context,
            "sql": retry_sql,
            "columns": retry_execution["columns"],
            "rows": retry_execution["rows"],
            "was_self_corrected": True
        }

    log_query(question, reasoning, sql, True, None)

    return {
        "question": question,
        "reasoning": reasoning,
        "tables_used": tables_used,
        "schema_context": schema_context,
        "sql": sql,
        "columns": execution["columns"],
        "rows": execution["rows"],
        "was_self_corrected": False
    }