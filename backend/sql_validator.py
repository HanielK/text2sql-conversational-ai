import re
from typing import Tuple

from backend.config import settings

BANNED_SQL_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "truncate",
    "grant", "revoke", "create", "replace", "merge", "call"
}


def normalize_sql(sql: str) -> str:
    sql = sql.strip().strip(";")
    sql = re.sub(r"\s+", " ", sql)
    return sql


def contains_banned_keyword(sql: str) -> Tuple[bool, str]:
    lowered = sql.lower()
    for keyword in BANNED_SQL_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return True, keyword
    return False, ""


def enforce_select_only(sql: str) -> Tuple[bool, str]:
    lowered = sql.lower().strip()
    if not lowered.startswith("select"):
        return False, "Only SELECT statements are allowed."
    return True, ""


def detect_multi_statement(sql: str) -> Tuple[bool, str]:
    cleaned = sql.strip()
    if ";" in cleaned:
        return False, "Multiple SQL statements are not allowed."
    return True, ""


def apply_limit_if_missing(sql: str, row_limit: int | None = None) -> str:
    row_limit = row_limit or settings.SQL_ROW_LIMIT
    lowered = sql.lower()

    if re.search(r"\blimit\s+\d+\b", lowered):
        return sql

    return f"{sql} LIMIT {row_limit}"


def validate_sql(sql: str) -> Tuple[bool, str, str]:
    sql = normalize_sql(sql)

    ok, msg = enforce_select_only(sql)
    if not ok:
        return False, msg, sql

    ok, msg = detect_multi_statement(sql)
    if not ok:
        return False, msg, sql

    banned, keyword = contains_banned_keyword(sql)
    if banned:
        return False, f"Disallowed SQL keyword detected: {keyword}", sql

    sql = apply_limit_if_missing(sql)
    return True, "SQL is valid.", sql