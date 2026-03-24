import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "feedback"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FEEDBACK_FILE = DATA_DIR / "feedback.json"
FAILURES_FILE = DATA_DIR / "failures.json"


# --------------------------------------------------
# Ensure files exist (🔥 CRITICAL FIX)
# --------------------------------------------------

def _ensure_file(path: Path):
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)


_ensure_file(FEEDBACK_FILE)
_ensure_file(FAILURES_FILE)


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"⚠️ Failed to read {path}: {e}")
        return []


def _write_json_list(path: Path, items: list[dict[str, Any]]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)
    except Exception as e:
        print(f"❌ Failed to write {path}: {e}")


# --------------------------------------------------
# Feedback
# --------------------------------------------------

def save_feedback(
    request_id: str,
    session_id: str,
    question: str,
    sql: str,
    plan: dict[str, Any],
    rating: str,
    comments: str = "",
    route: str = "sql",
    confidence: float | None = None,
) -> dict[str, Any]:

    items = _read_json_list(FEEDBACK_FILE)

    if confidence is None and isinstance(plan, dict):
        confidence = plan.get("confidence")

    record = {
        "id": len(items) + 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "session_id": session_id,
        "question": question,
        "sql": sql,
        "plan": plan or {},
        "rating": rating,
        "comments": comments,
        "route": route,
        "confidence": confidence,
    }

    items.append(record)
    _write_json_list(FEEDBACK_FILE, items)

    return record


# --------------------------------------------------
# Failure Tracking (🔥 DEMO CRITICAL)
# --------------------------------------------------

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

    print(f"❌ FAILURE SAVED: {question}")  # 🔥 demo visibility

    return record


# --------------------------------------------------
# Getters
# --------------------------------------------------

def list_feedback() -> list[dict[str, Any]]:
    data = _read_json_list(FEEDBACK_FILE)
    print(f"📊 Loaded feedback: {len(data)} items")  # optional debug
    return data


def list_failures() -> list[dict[str, Any]]:
    data = _read_json_list(FAILURES_FILE)

    print("📂 FAILURES FILE:", FAILURES_FILE)   # 🔥 DEBUG
    print(f"📊 Loaded failures: {len(data)} items")

    return data