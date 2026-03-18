import json
import time
from typing import Any, Dict

from backend.feedback_store import save_failure_case
from backend.logging_utils import logger, log_event, new_request_id
from backend.query_analyzer import analyze_question
from backend.planner import build_query_plan
from backend.sql_validator import validate_sql
from backend.sql_generator import generate_sql_from_plan
from backend.embeddings import retrieve_relevant_schema, retrieve_relevant_columns


def run_text_to_sql_pipeline(question: str, session_id: str | None = None) -> Dict[str, Any]:
    request_id = new_request_id()
    started = time.perf_counter()

    log_event(
        logger,
        "Pipeline started",
        request_id=request_id,
        stage="pipeline_start",
        extra={
            "question": question,
            "session_id": session_id,
        },
    )

    try:
        # -------------------------------------------------
        # 1. Analyze question (route + confidence + rewrite + ambiguity)
        # -------------------------------------------------
        t_analyze = time.perf_counter()
        analysis = analyze_question(question)

        log_event(
            logger,
            "Question analysis complete",
            request_id=request_id,
            stage="question_analysis",
            extra={
                "duration_ms": round((time.perf_counter() - t_analyze) * 1000, 2),
                "analysis": analysis,
            },
        )

        rewritten_question = analysis.get("rewritten_question", question)
        route = analysis.get("route", "sql")
        confidence = analysis.get("confidence", 0.5)
        is_ambiguous = analysis.get("is_ambiguous", False)
        clarification_question = analysis.get("clarification_question", "")

        if is_ambiguous:
            log_event(
                logger,
                "Question requires clarification",
                request_id=request_id,
                stage="clarification_required",
                status="needs_clarification",
                extra={
                    "clarification_question": clarification_question,
                    "rewritten_question": rewritten_question,
                    "route": route,
                    "confidence": confidence,
                },
            )

            return {
                "success": False,
                "needs_clarification": True,
                "request_id": request_id,
                "question": question,
                "rewritten_question": rewritten_question,
                "route": route,
                "confidence": confidence,
                "clarification_question": clarification_question,
                "analysis": analysis,
                "error": "Clarification required before SQL generation.",
            }

        # -------------------------------------------------
        # 2. Schema retrieval
        # -------------------------------------------------
        t0 = time.perf_counter()
        schema_text = retrieve_relevant_schema(rewritten_question)
        column_text = retrieve_relevant_columns(rewritten_question)

        log_event(
            logger,
            "Schema retrieval complete",
            request_id=request_id,
            stage="schema_retrieval",
            extra={
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "schema_preview": str(schema_text)[:1500],
                "column_preview": str(column_text)[:1500],
                "rewritten_question": rewritten_question,
            },
        )

        # -------------------------------------------------
        # 3. Query planning
        # -------------------------------------------------
        t1 = time.perf_counter()
        plan = build_query_plan(
            question=rewritten_question,
            schema_text=schema_text,
            column_text=column_text,
        )

        log_event(
            logger,
            "Query plan built",
            request_id=request_id,
            stage="query_planning",
            extra={
                "duration_ms": round((time.perf_counter() - t1) * 1000, 2),
                "plan": plan,
            },
        )

        # -------------------------------------------------
        # 4. SQL generation
        # -------------------------------------------------
        t2 = time.perf_counter()
        raw_sql = generate_sql_from_plan(
            question=rewritten_question,
            schema_text=schema_text,
            column_text=column_text,
            plan_json=json.dumps(plan, indent=2),
        )

        log_event(
            logger,
            "SQL generated",
            request_id=request_id,
            stage="sql_generation",
            extra={
                "duration_ms": round((time.perf_counter() - t2) * 1000, 2),
                "raw_sql": raw_sql,
            },
        )

        # -------------------------------------------------
        # 5. SQL validation
        # -------------------------------------------------
        t3 = time.perf_counter()
        is_valid, validation_message, safe_sql = validate_sql(raw_sql)

        log_event(
            logger,
            "SQL validation complete",
            request_id=request_id,
            stage="sql_validation",
            status="ok" if is_valid else "failed",
            extra={
                "duration_ms": round((time.perf_counter() - t3) * 1000, 2),
                "validation_message": validation_message,
                "safe_sql": safe_sql,
            },
        )

        # -------------------------------------------------
        # 6. Validation failure
        # -------------------------------------------------
        if not is_valid:
            save_failure_case(
                request_id=request_id,
                session_id=session_id or "unknown",
                question=question,
                route=route,
                error=validation_message,
                sql=raw_sql,
                plan=plan,
            )

            return {
                "success": False,
                "needs_clarification": False,
                "request_id": request_id,
                "question": question,
                "rewritten_question": rewritten_question,
                "route": route,
                "confidence": confidence,
                "analysis": analysis,
                "plan": plan,
                "raw_sql": raw_sql,
                "safe_sql": safe_sql,
                "error": validation_message,
            }

        # -------------------------------------------------
        # 7. Success
        # -------------------------------------------------
        total_ms = round((time.perf_counter() - started) * 1000, 2)

        log_event(
            logger,
            "Pipeline completed",
            request_id=request_id,
            stage="pipeline_complete",
            extra={"duration_ms": total_ms},
        )

        return {
            "success": True,
            "needs_clarification": False,
            "request_id": request_id,
            "question": question,
            "rewritten_question": rewritten_question,
            "route": route,
            "confidence": confidence,
            "analysis": analysis,
            "plan": plan,
            "raw_sql": raw_sql,
            "safe_sql": safe_sql,
            "schema_text": schema_text,
            "column_text": column_text,
            "duration_ms": total_ms,
        }

    except Exception as exc:
        save_failure_case(
            request_id=request_id,
            session_id=session_id or "unknown",
            question=question,
            route="sql",
            error=str(exc),
        )

        log_event(
            logger,
            "Pipeline failed",
            request_id=request_id,
            stage="pipeline_error",
            status="failed",
            extra={"error": str(exc)},
        )

        return {
            "success": False,
            "needs_clarification": False,
            "request_id": request_id,
            "question": question,
            "error": str(exc),
        }