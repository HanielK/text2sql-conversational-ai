import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "conversation_memory"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_session_file(session_id: str) -> Path:
    return DATA_DIR / f"{session_id}.json"


def load_session_memory(session_id: str) -> Dict[str, Any]:
    path = _get_session_file(session_id)

    if not path.exists():
        return {"history": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"history": []}


def save_session_memory(session_id: str, memory: Dict[str, Any]) -> None:
    path = _get_session_file(session_id)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


def add_interaction(
    session_id: str,
    question: str,
    rewritten_question: str,
    sql: str,
    plan: Dict[str, Any],
    route: str,
):
    memory = load_session_memory(session_id)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "rewritten_question": rewritten_question,
        "sql": sql,
        "plan": plan,
        "route": route,
    }

    memory["history"].append(entry)

    # keep only last 5 interactions
    memory["history"] = memory["history"][-5:]

    save_session_memory(session_id, memory)


def get_last_interaction(session_id: str) -> Dict[str, Any] | None:
    memory = load_session_memory(session_id)

    if not memory["history"]:
        return None

    return memory["history"][-1]
