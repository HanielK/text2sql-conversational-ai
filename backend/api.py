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
from backend.feedback_store import save_feedback, list_feedback, list_failures
from backend.golden_queries import add_golden_query, list_golden_queries
from backend.conversation_memory import (
    add_interaction,
    get_last_interaction
)

# -----------------------------------------------------
# Load environment variables
# -----------------------------------------------------

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

app = FastAPI(title="AI SQL Copilot")


# -----------------------------------------------------
# Models
# -----------------------------------------------------

class QueryRequest(BaseModel):
    question: str
    session_id: str


class FeedbackRequest(BaseModel):
    request_id: str
    session_id: str
    question: str
    sql: str = ""
    plan: dict = {}
    rating: str
    comments: str = ""
    route: str = "sql"


# -----------------------------------------------------
# Helpers
# -----------------------------------------------------

def detect_chart(columns, rows):
    if not rows or len(columns) < 2:
        return None

    if isinstance(rows[0][1], (int, float)):
        return {
            "chart_type": "bar",
            "x": columns[0],
            "y": columns[1]
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


# ---------------- FOLLOW-UP DETECTION ----------------

def is_follow_up_question(question: str) -> bool:
    follow_up_phrases = [
        "now", "instead", "also", "same", "previous",
        "that", "those", "it", "filter", "change", "update"
    ]

    q = question.lower()
    return any(q.startswith(p) or f" {p} " in q for p in follow_up_phrases)


def enrich_with_context(question: str, session_id: str) -> str:
    last = get_last_interaction(session_id)

    if not last:
        return question

    return f"""
Previous question: {last['rewritten_question']}

Previous SQL logic:
{last['sql']}

Follow-up question:
{question}

Rewrite this into a complete standalone question.
"""


# -----------------------------------------------------
# Metrics Endpoint
# -----------------------------------------------------

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


# -----------------------------------------------------
# MAIN QUERY ENDPOINT
# -----------------------------------------------------

@app.post("/query")
def query_ai(payload: QueryRequest):
    original_question = payload.question.strip()
    session_id = payload.session_id

    if not original_question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # -------- STEP 4: Follow-up handling --------
    question = original_question

    if is_follow_up_question(original_question):
        question = enrich_with_context(original_question, session_id)

    start_time = time.time()
    routed_guess = route_question(question)

    # ---------------- DOC ----------------
    if routed_guess == "doc":
        doc_result = answer_from_docs(question)
        elapsed = time.time() - start_time
        log_metric(session_id, original_question, "doc", True, elapsed)

        return {
            "route": "doc",
            "question": original_question,
            "reasoning": doc_result["reasoning"],
            "columns": ["answer"],
            "rows": [[doc_result["answer"]]],
            "sources": doc_result["sources"],
            "chart": None
        }

    # ---------------- SQL / HYBRID ----------------
    if routed_guess in {"sql", "hybrid"}:
        pipeline_result = run_text_to_sql_pipeline(question, session_id=session_id)

        # ---- Clarification ----
        if pipeline_result.get("needs_clarification"):
            return {
                "success": False,
                "needs_clarification": True,
                "request_id": pipeline_result["request_id"],
                "route": pipeline_result.get("route"),
                "confidence": pipeline_result.get("confidence"),
                "question": original_question,
                "rewritten_question": pipeline_result.get("rewritten_question"),
                "clarification_question": pipeline_result.get("clarification_question"),
                "analysis": pipeline_result.get("analysis"),
            }

        if not pipeline_result["success"]:
            raise HTTPException(status_code=400, detail=pipeline_result.get("error"))

        final_route = pipeline_result.get("route", routed_guess)
        sql = pipeline_result["safe_sql"]
        plan = pipeline_result["plan"]
        rewritten_question = pipeline_result.get("rewritten_question", question)
        confidence = pipeline_result.get("confidence", 0.0)

        execution = execute_sql(sql)
        elapsed = time.time() - start_time

        if not execution["success"]:
            raise HTTPException(status_code=500, detail=execution["error"])

        chart = detect_chart(execution["columns"], execution["rows"])

        # -------- SAVE MEMORY --------
        add_interaction(
            session_id=session_id,
            question=original_question,
            rewritten_question=rewritten_question,
            sql=sql,
            plan=plan,
            route=final_route,
        )

        log_metric(session_id, original_question, final_route, True, elapsed)

        return {
            "route": final_route,
            "question": original_question,
            "rewritten_question": rewritten_question,
            "confidence": confidence,
            "plan": plan,
            "sql": sql,
            "columns": execution["columns"],
            "rows": execution["rows"],
            "chart": chart,
            "request_id": pipeline_result["request_id"]
        }

    raise HTTPException(status_code=500, detail="Unable to route question.")


# -----------------------------------------------------
# FEEDBACK ENDPOINT
# -----------------------------------------------------

@app.post("/feedback")
def submit_feedback(payload: FeedbackRequest):
    record = save_feedback(**payload.dict())

    if payload.rating == "correct" and payload.sql:
        golden = add_golden_query(
            question=payload.question,
            sql=payload.sql,
            plan=payload.plan,
            tables_used=payload.plan.get("tables_needed", []),
        )
        return {
            "success": True,
            "golden_query_added": True,
            "golden_query": golden,
        }

    return {"success": True}


# -----------------------------------------------------
# ADMIN ENDPOINTS
# -----------------------------------------------------

@app.get("/feedback")
def get_feedback():
    return {"items": list_feedback()}


@app.get("/failures")
def get_failures():
    return {"items": list_failures()}


@app.get("/golden-queries")
def get_golden_queries():
    return {"items": list_golden_queries()}

