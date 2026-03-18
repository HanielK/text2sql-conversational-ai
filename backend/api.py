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


env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

app = FastAPI(title="AI SQL Copilot")


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
    routed_guess = route_question(question)

    if routed_guess == "doc":
        doc_result = answer_from_docs(question)
        elapsed = time.time() - start_time
        log_metric(session_id, question, "doc", True, elapsed)

        return {
            "route": "doc",
            "question": question,
            "reasoning": doc_result["reasoning"],
            "tables_used": [],
            "sql": "",
            "columns": ["answer"],
            "rows": [[doc_result["answer"]]],
            "chart": None,
            "sources": doc_result["sources"],
            "was_self_corrected": False,
        }

    if routed_guess in {"sql", "hybrid"}:
        pipeline_result = run_text_to_sql_pipeline(question, session_id=session_id)

        if pipeline_result.get("needs_clarification"):
            log_metric(session_id, question, pipeline_result.get("route", routed_guess), False, time.time() - start_time)
            return {
                "success": False,
                "needs_clarification": True,
                "request_id": pipeline_result["request_id"],
                "route": pipeline_result.get("route", routed_guess),
                "confidence": pipeline_result.get("confidence", 0.0),
                "question": question,
                "rewritten_question": pipeline_result.get("rewritten_question", question),
                "clarification_question": pipeline_result.get("clarification_question", ""),
                "analysis": pipeline_result.get("analysis", {}),
            }

        if not pipeline_result["success"]:
            log_metric(session_id, question, pipeline_result.get("route", routed_guess), False, time.time() - start_time)
            raise HTTPException(status_code=400, detail=pipeline_result.get("error"))

        final_route = pipeline_result.get("route", routed_guess)
        sql = pipeline_result["safe_sql"]
        plan = pipeline_result["plan"]
        confidence = pipeline_result.get("confidence", 0.0)
        rewritten_question = pipeline_result.get("rewritten_question", question)
        analysis = pipeline_result.get("analysis", {})

        reasoning = (
            plan.get("reasoning_summary", "")
            + "\n\nIntent: " + plan.get("intent", "")
            + "\nRoute Confidence: " + str(confidence)
        )

        tables_used = plan.get("tables_needed", [])
        execution = execute_sql(sql)
        elapsed = time.time() - start_time

        if not execution["success"]:
            log_metric(session_id, question, final_route, False, elapsed)
            raise HTTPException(status_code=500, detail=execution["error"])

        chart = detect_chart(execution["columns"], execution["rows"])

        if final_route == "hybrid":
            doc_rows = retrieve_relevant_docs(question, top_k=3)
            doc_context = "\n\n".join([row[2] for row in doc_rows]) if doc_rows else "No document context found."

            reasoning = (
                reasoning
                + "\n\nHybrid mode combined SQL output with supporting document context."
                + f"\n\nDocument context preview:\n{doc_context[:1200]}"
            )

            result_payload = {
                "columns": execution["columns"],
                "rows": execution["rows"][:10]
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

            log_metric(session_id, question, final_route, True, elapsed)

            return {
                "route": final_route,
                "question": question,
                "rewritten_question": rewritten_question,
                "confidence": confidence,
                "analysis": analysis,
                "plan": plan,
                "reasoning": reasoning,
                "tables_used": tables_used,
                "sql": sql,
                "columns": execution["columns"],
                "rows": execution["rows"],
                "chart": chart,
                "sources": [row[0] for row in doc_rows],
                "request_id": pipeline_result["request_id"],
                "was_self_corrected": execution.get("was_self_corrected", False)
            }

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

        log_metric(session_id, question, final_route, True, elapsed)

        return {
            "route": final_route,
            "question": question,
            "rewritten_question": rewritten_question,
            "confidence": confidence,
            "analysis": analysis,
            "plan": plan,
            "reasoning": reasoning,
            "tables_used": tables_used,
            "sql": sql,
            "columns": execution["columns"],
            "rows": execution["rows"],
            "chart": chart,
            "request_id": pipeline_result["request_id"],
            "was_self_corrected": execution.get("was_self_corrected", False)
        }

    log_metric(session_id, question, "unknown", False, time.time() - start_time)
    raise HTTPException(status_code=500, detail="Unable to route question.")


@app.post("/feedback")
def submit_feedback(payload: FeedbackRequest):
    if payload.rating not in {"correct", "incorrect"}:
        raise HTTPException(status_code=400, detail="rating must be 'correct' or 'incorrect'.")

    record = save_feedback(
        request_id=payload.request_id,
        session_id=payload.session_id,
        question=payload.question,
        sql=payload.sql,
        plan=payload.plan,
        rating=payload.rating,
        comments=payload.comments,
        route=payload.route,
    )

    if payload.rating == "correct" and payload.sql:
        golden = add_golden_query(
            question=payload.question,
            sql=payload.sql,
            plan=payload.plan,
            tables_used=payload.plan.get("tables_needed", []),
        )
        return {
            "success": True,
            "feedback": record,
            "golden_query_added": True,
            "golden_query": golden,
        }

    return {
        "success": True,
        "feedback": record,
        "golden_query_added": False,
    }


@app.get("/feedback")
def get_feedback():
    return {"items": list_feedback()}


@app.get("/failures")
def get_failures():
    return {"items": list_failures()}


@app.get("/golden-queries")
def get_golden_queries():
    return {"items": list_golden_queries()}