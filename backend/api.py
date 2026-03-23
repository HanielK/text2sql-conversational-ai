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
from backend.conversation_memory import add_interaction, get_last_interaction
from backend.query_analyzer import analyze_follow_up
from backend.response_builder import build_structured_response


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
    confidence: float | None = None  # 🔥 NEW


# -----------------------------------------------------
# Helpers
# -----------------------------------------------------

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


def maybe_enrich_follow_up(question: str, session_id: str) -> tuple[str, dict]:
    last = get_last_interaction(session_id)

    if not last:
        return question, {
            "is_follow_up": False,
            "standalone_question": question,
            "reasoning_summary": "No prior interaction found.",
        }

    analysis = analyze_follow_up(
        new_question=question,
        previous_question=last.get("question", ""),
        previous_rewritten_question=last.get("rewritten_question", ""),
        previous_sql=last.get("sql", ""),
        previous_plan=last.get("plan", {}),
    )

    standalone_question = analysis.get("standalone_question", question)
    return standalone_question, analysis


# -----------------------------------------------------
# Metrics
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
# MAIN QUERY
# -----------------------------------------------------

@app.post("/query")
def query_ai(payload: QueryRequest):
    original_question = payload.question.strip()
    session_id = payload.session_id

    if not original_question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    start_time = time.time()

    enriched_question, follow_up_analysis = maybe_enrich_follow_up(original_question, session_id)
    routed_guess = route_question(enriched_question)

    # ---------------- DOC ----------------
    if routed_guess == "doc":
        doc_result = answer_from_docs(enriched_question)

        elapsed = time.time() - start_time
        log_metric(session_id, original_question, "doc", True, elapsed)

        response = {
            "success": True,
            "route": "doc",
            "question": original_question,
            "rewritten_question": enriched_question,
            "confidence": 1.0,
            "analysis": {"follow_up_analysis": follow_up_analysis},
            "plan": {},
            "sql": "",
            "result": {
                "type": "text",
                "columns": ["answer"],
                "rows": [[doc_result["answer"]]],
                "row_count": 1,
            },
            "chart": None,
            "insights": doc_result["reasoning"],
            "follow_ups": [
                "Can you show the relevant policy section?",
                "Can you summarize the key rules?",
                "Are there any exceptions mentioned?",
            ],
            "sources": doc_result["sources"],
            "request_id": "",
        }

        add_interaction(
            session_id=session_id,
            question=original_question,
            rewritten_question=enriched_question,
            sql="",
            plan={},
            route="doc",
        )

        return response

    # ---------------- SQL / HYBRID ----------------
    if routed_guess in {"sql", "hybrid"}:
        pipeline_result = run_text_to_sql_pipeline(enriched_question, session_id=session_id)

        if pipeline_result.get("needs_clarification"):
            return {
                "success": False,
                "needs_clarification": True,
                "request_id": pipeline_result["request_id"],
                "route": pipeline_result.get("route", routed_guess),
                "confidence": pipeline_result.get("confidence", 0.0),
                "question": original_question,
                "rewritten_question": pipeline_result.get("rewritten_question", enriched_question),
                "clarification_question": pipeline_result.get("clarification_question", ""),
                "analysis": {
                    **pipeline_result.get("analysis", {}),
                    "follow_up_analysis": follow_up_analysis,
                },
            }

        if not pipeline_result["success"]:
            raise HTTPException(status_code=400, detail=pipeline_result.get("error"))

        final_route = pipeline_result.get("route", routed_guess)
        sql = pipeline_result["safe_sql"]
        plan = pipeline_result["plan"]
        rewritten_question = pipeline_result.get("rewritten_question", enriched_question)
        confidence = pipeline_result.get("confidence", 0.0)

        execution = execute_sql(sql)

        if not execution["success"]:
            raise HTTPException(status_code=500, detail=execution["error"])

        sources = []

        if final_route == "hybrid":
            doc_rows = retrieve_relevant_docs(original_question, top_k=3)
            sources = [row[0] for row in doc_rows]

        # SAVE MEMORY
        add_interaction(
            session_id=session_id,
            question=original_question,
            rewritten_question=rewritten_question,
            sql=sql,
            plan=plan,
            route=final_route,
        )

        # LOG METRICS
        elapsed = time.time() - start_time
        log_metric(session_id, original_question, final_route, True, elapsed)

        return build_structured_response(
            route=final_route,
            original_question=original_question,
            rewritten_question=rewritten_question,
            confidence=confidence,
            analysis={"follow_up_analysis": follow_up_analysis},
            plan=plan,
            sql=sql,
            columns=execution["columns"],
            rows=execution["rows"],
            request_id=pipeline_result["request_id"],
            sources=sources,
        )

    raise HTTPException(status_code=500, detail="Unable to route question.")


# -----------------------------------------------------
# FEEDBACK + AUTO PROMOTE 🔥
# -----------------------------------------------------

@app.post("/feedback")
def submit_feedback(payload: FeedbackRequest):

    if payload.rating not in {"correct", "incorrect"}:
        raise HTTPException(status_code=400, detail="rating must be 'correct' or 'incorrect'.")

    # 🔥 FIX: use explicit confidence or fallback
    confidence = payload.confidence

    record = save_feedback(
        request_id=payload.request_id,
        session_id=payload.session_id,
        question=payload.question,
        sql=payload.sql,
        plan={
            **payload.plan,
            "confidence": payload.plan.get("confidence", 0)
        },
        rating=payload.rating,
        comments=payload.comments,
        route=payload.route,
    )

    # ---------------- AUTO PROMOTE ----------------
    if payload.rating == "correct" and payload.sql:

        feedback_items = list_feedback()

        success_count = sum(
            1 for f in feedback_items
            if f["question"] == payload.question and f["rating"] == "correct"
        )

        existing_goldens = list_golden_queries()

        already_exists = any(g["question"] == payload.question for g in existing_goldens)

        if success_count >= 3 and not already_exists:

            golden = add_golden_query(
                question=payload.question,
                sql=payload.sql,
                plan=payload.plan,
                tables_used=payload.plan.get("tables_needed", []),
            )

            return {
                "success": True,
                "auto_promoted": True,
                "count": success_count,
                "golden_query": golden,
            }

    return {
        "success": True,
        "auto_promoted": False,
    }

# -----------------------------------------------------
# GOLDEN QUERY (MANUAL PROMOTION) 🔥
# -----------------------------------------------------

@app.post("/golden-queries")
def save_golden_query(payload: dict):

    if not payload.get("question") or not payload.get("sql"):
        raise HTTPException(status_code=400, detail="question and sql are required")

    existing = list_golden_queries()

    # Prevent duplicates
    already_exists = any(
        g["question"] == payload["question"] for g in existing
    )

    if already_exists:
        return {
            "success": True,
            "message": "Already exists in golden queries"
        }

    record = add_golden_query(
        question=payload["question"],
        sql=payload["sql"],
        plan=payload.get("plan", {}),
        tags=payload.get("tags", []),
        tables_used=payload.get("tables_used", []),
    )

    print(f"🔥 MANUAL GOLDEN SAVED: {payload['question']}")

    return {
        "success": True,
        "item": record
    }
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

