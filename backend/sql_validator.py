import re
from typing import Tuple

from backend.config import settings

BANNED_SQL_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "truncate",
    "grant", "revoke", "create", "replace", "merge", "call"
}


# ---------------------------------------------------------
# CLEAN SQL
# ---------------------------------------------------------

def normalize_sql(sql: str) -> str:
    sql = sql.strip().strip(";")
    sql = re.sub(r"\s+", " ", sql)
    return sql


# ---------------------------------------------------------
# SAFETY CHECKS
# ---------------------------------------------------------

def contains_banned_keyword(sql: str) -> Tuple[bool, str]:
    lowered = sql.lower()
    for keyword in BANNED_SQL_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return True, keyword
    return False, ""


def enforce_select_only(sql: str) -> Tuple[bool, str]:
    lowered = sql.lower().strip()

    # 🔥 Allow CTEs (WITH clause)
    if lowered.startswith("with"):
        return True, ""

    if not lowered.startswith("select"):
        return False, "Only SELECT statements are allowed."

    return True, ""


def detect_multi_statement(sql: str) -> Tuple[bool, str]:
    cleaned = sql.strip()

    # 🔥 allow trailing semicolon but not multiple
    if cleaned.count(";") > 0:
        return False, "Multiple SQL statements are not allowed."

    return True, ""


# ---------------------------------------------------------
# LIMIT CONTROL
# ---------------------------------------------------------

def apply_limit_if_missing(sql: str, row_limit: int | None = None) -> str:
    row_limit = row_limit or settings.SQL_ROW_LIMIT
    lowered = sql.lower()

    # already has limit
    if re.search(r"\blimit\s+\d+\b", lowered):
        return sql

    # 🔥 avoid breaking ORDER BY
    if "order by" in lowered:
        return f"{sql} LIMIT {row_limit}"

    return f"{sql} LIMIT {row_limit}"


# ---------------------------------------------------------
# OPTIONAL HARDENING (🔥 NEW)
# ---------------------------------------------------------

def enforce_no_select_star(sql: str) -> Tuple[bool, str]:
    if re.search(r"select\s+\*", sql.lower()):
        return False, "SELECT * is not allowed. Use explicit columns."
    return True, ""


# ---------------------------------------------------------
# MAIN VALIDATION
# ---------------------------------------------------------

def validate_sql(sql: str) -> Tuple[bool, str, str]:
    sql = normalize_sql(sql)

    # SELECT / WITH only
    ok, msg = enforce_select_only(sql)
    if not ok:
        return False, msg, sql

    # No multi statements
    ok, msg = detect_multi_statement(sql)
    if not ok:
        return False, msg, sql

    # No dangerous keywords
    banned, keyword = contains_banned_keyword(sql)
    if banned:
        return False, f"Disallowed SQL keyword detected: {keyword}", sql

    # 🔥 Optional: enforce no SELECT *
    if getattr(settings, "ENFORCE_NO_SELECT_STAR", False):
        ok, msg = enforce_no_select_star(sql)
        if not ok:
            return False, msg, sql

    # Apply LIMIT
    sql = apply_limit_if_missing(sql)

    return True, "SQL is valid.", sql