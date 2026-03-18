import os
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from psycopg.types.json import Jsonb
from backend.db import get_connection
from backend.router import route_question
from backend.sql_executor import execute_sql
from backend.document_rag import answer_from_docs, retrieve_relevant_docs
from backend.pipeline import run_text_to_sql_pipeline


# -----------------------------------------------------
# Load environment variables from project root
# -----------------------------------------------------

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

app = FastAPI(title="AI SQL Copilot")


class QueryRequest(BaseModel):
    question: str
    session_id: str


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


def log_metric(session_id, question, route, success, execution_time):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO evaluation_metrics
                    (session_id, question, route, success, execution_time)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (session_id, question, route, success, execution_time)
                )
                conn.commit()
    except Exception as e:
        print("Metric logging failed:", str(e))


@app.get("/metrics")
def get_metrics():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_queries,
                    COALESCE(AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END), 0) AS success_rate,
                    COALESCE(AVG(execution_time), 0) AS avg_latency
                FROM evaluation_metrics
                """
            )
            row = cur.fetchone()

    return {
        "total_queries": int(row[0] or 0),
        "success_rate": round(float(row[1] or 0), 3),
        "avg_latency": round(float(row[2] or 0), 3)
    }


@app.post("/query")
def query_ai(payload: QueryRequest):
    question = payload.question.strip()
    session_id = payload.session_id

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    start_time = time.time()
    route = route_question(question)

    # -------------------------------------------------
    # SQL route
    # -------------------------------------------------
    
    if route == "sql":
        pipeline_result = run_text_to_sql_pipeline(question)

        if not pipeline_result["success"]:
            log_metric(session_id, question, route, False, time.time() - start_time)
            raise HTTPException(status_code=400, detail=pipeline_result.get("error"))

        sql = pipeline_result["safe_sql"]
        plan = pipeline_result["plan"]

        print("SAFE SQL FROM PIPELINE:\n", sql)
        print("PLAN:\n", plan)

        reasoning = (
            plan.get("reasoning_summary", "")
            + "\n\nIntent: " + plan.get("intent", "")
        )

        tables_used = plan.get("tables_needed", [])

        execution = execute_sql(sql)
        elapsed = time.time() - start_time

        if not execution["success"]:
            log_metric(session_id, question, route, False, elapsed)
            raise HTTPException(status_code=500, detail=execution["error"])

        result_payload = {
            "columns": execution["columns"],
            "rows": execution["rows"][:50]
        }

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
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
                            execution.get("execution_time", elapsed),
                            execution["success"],
                            Jsonb(result_payload)
                        )
                    )
                    conn.commit()
        except Exception as e:
            print("Query logging failed:", str(e))

        log_metric(session_id, question, route, True, elapsed)

        chart = detect_chart(execution["columns"], execution["rows"])

        return {
            "route": route,
            "question": question,
            "plan": plan,  # 🔥 IMPORTANT
            "reasoning": reasoning,
            "tables_used": tables_used,
            "sql": sql,
            "columns": execution["columns"],
            "rows": execution["rows"],
            "chart": chart,
            "request_id": pipeline_result["request_id"],  # 🔥 IMPORTANT
            "was_self_corrected": execution.get("was_self_corrected", False)
        }

    # -------------------------------------------------
    # Document route
    # -------------------------------------------------

    if route == "doc":
        doc_result = answer_from_docs(question)
        elapsed = time.time() - start_time
        log_metric(session_id, question, route, True, elapsed)

        return {
            "route": route,
            "question": question,
            "reasoning": doc_result["reasoning"],
            "tables_used": [],
            "sql": "",
            "columns": ["answer"],
            "rows": [[doc_result["answer"]]],
            "chart": None,
            "sources": doc_result["sources"],
            "was_self_corrected": False
        }

    # -------------------------------------------------
    # Hybrid route
    # -------------------------------------------------

    if route == "hybrid":
        pipeline_result = run_text_to_sql_pipeline(question)

        if not pipeline_result["success"]:
            log_metric(session_id, question, route, False, time.time() - start_time)
            raise HTTPException(status_code=400, detail=pipeline_result.get("error"))

        sql = pipeline_result["safe_sql"]
        plan = pipeline_result["plan"]

        reasoning = plan.get("reasoning_summary", "")
        tables_used = plan.get("tables_needed", [])

        execution = execute_sql(sql)
        elapsed = time.time() - start_time

        if not execution["success"]:
            log_metric(session_id, question, route, False, elapsed)
            raise HTTPException(status_code=500, detail=execution["error"])

        doc_rows = retrieve_relevant_docs(question, top_k=3)
        doc_context = "\n\n".join([row[2] for row in doc_rows]) if doc_rows else "No document context found."

        result_preview = {
            "columns": execution["columns"],
            "rows": execution["rows"][:10]
        }

        hybrid_reasoning = (
            reasoning
            + "\n\n"
            + "Hybrid mode combined SQL output with supporting document context."
            + "\n\n"
            + f"Document context preview:\n{doc_context[:1200]}"
        )

        log_metric(session_id, question, route, True, elapsed)

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
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
                            execution.get("execution_time", elapsed),
                            execution["success"],
                            Jsonb(result_preview)
                        )
                    )
                    conn.commit()
        except Exception as e:
            print("Query logging failed:", str(e))

        chart = detect_chart(execution["columns"], execution["rows"])

        return {
            "route": route,
            "question": question,
            "reasoning": hybrid_reasoning,
            "tables_used": tables_used,
            "sql": sql,
            "columns": execution["columns"],
            "rows": execution["rows"],
            "chart": chart,
            "sources": [row[0] for row in doc_rows],
            "was_self_corrected": execution.get("was_self_corrected", False)
        }

    log_metric(session_id, question, "unknown", False, time.time() - start_time)
    raise HTTPException(status_code=500, detail="Unable to route question.")