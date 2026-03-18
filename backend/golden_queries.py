import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from backend.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "golden_queries"
DATA_DIR.mkdir(parents=True, exist_ok=True)

GOLDEN_QUERIES_FILE = DATA_DIR / "golden_queries.json"


def _load_golden_queries() -> list[dict[str, Any]]:
    if not GOLDEN_QUERIES_FILE.exists():
        return []

    try:
        with open(GOLDEN_QUERIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_golden_queries(items: list[dict[str, Any]]) -> None:
    with open(GOLDEN_QUERIES_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def add_golden_query(
    question: str,
    sql: str,
    plan: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    tables_used: list[str] | None = None,
) -> dict[str, Any]:
    items = _load_golden_queries()

    record = {
        "id": len(items) + 1,
        "question": question,
        "sql": sql,
        "plan": plan or {},
        "tags": tags or [],
        "tables_used": tables_used or [],
    }

    items.append(record)
    _save_golden_queries(items)
    return record


def list_golden_queries() -> list[dict[str, Any]]:
    return _load_golden_queries()


def _embed_text(text: str) -> list[float]:
    response = client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def retrieve_similar_golden_queries(
    question: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    items = _load_golden_queries()
    if not items:
        return []

    query_embedding = _embed_text(question)
    scored = []

    for item in items:
        text = f"{item.get('question', '')}\n{item.get('sql', '')}"
        item_embedding = _embed_text(text)
        score = cosine_similarity(query_embedding, item_embedding)
        enriched = dict(item)
        enriched["similarity_score"] = round(score, 4)
        scored.append(enriched)

    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:top_k]