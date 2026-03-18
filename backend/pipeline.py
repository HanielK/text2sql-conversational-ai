import json
import time
from typing import Any, Dict

from backend.logging_utils import logger, log_event, new_request_id
from backend.planner import build_query_plan
from backend.sql_validator import validate_sql
from backend.sql_generator import generate_sql_from_plan

# existing imports from your app
from backend.embeddings import retrieve_relevant_schema, retrieve_relevant_columns


def run_text_to_sql_pipeline(question: str) -> Dict[str, Any]:
    request_id = new_request_id()
    started = time.perf_counter()

    log_event(
        logger,
        "Pipeline started",
        request_id=request_id,
        stage="pipeline_start",
        extra={"question": question},
    )

    try:
        # 1. Schema retrieval
        t0 = time.perf_counter()
        schema_text = retrieve_relevant_schema(question)
        column_text = retrieve_relevant_columns(question)

        log_event(
            logger,
            "Schema retrieval complete",
            request_id=request_id,
            stage="schema_retrieval",
            extra={
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "schema_preview": str(schema_text)[:1500],
                "column_preview": str(column_text)[:1500],
            },
        )

        # 2. Query planning
        t1 = time.perf_counter()
        plan = build_query_plan(
            question=question,
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

        # 3. SQL generation
        t2 = time.perf_counter()
        raw_sql = generate_sql_from_plan(
            question=question,
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

        # 4. SQL validation
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

        if not is_valid:
            return {
                "success": False,
                "request_id": request_id,
                "question": question,
                "plan": plan,
                "raw_sql": raw_sql,
                "safe_sql": safe_sql,
                "error": validation_message,
            }

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
            "request_id": request_id,
            "question": question,
            "plan": plan,
            "raw_sql": raw_sql,
            "safe_sql": safe_sql,
            "schema_text": schema_text,
            "column_text": column_text,
            "duration_ms": total_ms,
        }

    except Exception as exc:
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
            "request_id": request_id,
            "question": question,
            "error": str(exc),
        }