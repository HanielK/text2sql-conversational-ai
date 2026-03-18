import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "feedback"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FEEDBACK_FILE = DATA_DIR / "feedback.json"
FAILURES_FILE = DATA_DIR / "failures.json"


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _write_json_list(path: Path, items: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def save_feedback(
    request_id: str,
    session_id: str,
    question: str,
    sql: str,
    plan: dict[str, Any],
    rating: str,
    comments: str = "",
    route: str = "sql",
) -> dict[str, Any]:
    items = _read_json_list(FEEDBACK_FILE)

    record = {
        "id": len(items) + 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "session_id": session_id,
        "question": question,
        "sql": sql,
        "plan": plan,
        "rating": rating,
        "comments": comments,
        "route": route,
    }

    items.append(record)
    _write_json_list(FEEDBACK_FILE, items)
    return record


def save_failure_case(
    request_id: str,
    session_id: str,
    question: str,
    route: str,
    error: str,
    sql: str = "",
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items = _read_json_list(FAILURES_FILE)

    record = {
        "id": len(items) + 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "session_id": session_id,
        "question": question,
        "route": route,
        "error": error,
        "sql": sql,
        "plan": plan or {},
    }

    items.append(record)
    _write_json_list(FAILURES_FILE, items)
    return record


def list_feedback() -> list[dict[str, Any]]:
    return _read_json_list(FEEDBACK_FILE)


def list_failures() -> list[dict[str, Any]]:
    return _read_json_list(FAILURES_FILE)