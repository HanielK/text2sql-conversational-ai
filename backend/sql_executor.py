import os
import psycopg
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from backend.config import settings

from backend.sql_validator import validate_sql  # 🔥 NEW

# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found")

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------
# SQL Repair (UPGRADED)
# ---------------------------------------------------------

def repair_sql(original_sql: str, error_message: str):

    prompt = f"""
You are a PostgreSQL expert.

Fix the SQL query below.

STRICT RULES:
- Return ONLY a valid SELECT query
- Do NOT include explanation
- Do NOT use dangerous statements

SQL:
{original_sql}

Error:
{error_message}
"""

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": "You fix SQL queries."},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content.strip()


# ---------------------------------------------------------
# Execute SQL (PRODUCTION SAFE)
# ---------------------------------------------------------

def execute_sql(sql: str, allow_repair: bool = True):

    # 🔥 STEP 1: Validate BEFORE execution
    is_valid, msg, sql = validate_sql(sql)

    if not is_valid:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": msg,
            "was_self_corrected": False
        }

    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()

    try:

        cur.execute(sql)

        rows = []
        columns = []

        if cur.description:
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

        conn.commit()

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "error": None,
            "was_self_corrected": False
        }

    except Exception as e:

        conn.rollback()
        error_message = str(e)

        # -------------------------------------------------
        # 🔥 SELF-CORRECT LOOP (SAFE)
        # -------------------------------------------------

        if allow_repair:

            try:
                fixed_sql = repair_sql(sql, error_message)

                print("\n🔧 SQL SELF-REPAIR TRIGGERED")
                print("Original:", sql)
                print("Error:", error_message)
                print("Fixed:", fixed_sql)

                # 🔥 VALIDATE FIXED SQL BEFORE EXECUTION
                is_valid, msg, fixed_sql = validate_sql(fixed_sql)

                if not is_valid:
                    return {
                        "success": False,
                        "columns": [],
                        "rows": [],
                        "error": f"Repair failed validation: {msg}",
                        "was_self_corrected": False
                    }

                result = execute_sql(fixed_sql, allow_repair=False)

                result["was_self_corrected"] = True
                result["corrected_sql"] = fixed_sql

                return result

            except Exception as repair_error:

                return {
                    "success": False,
                    "columns": [],
                    "rows": [],
                    "error": str(repair_error),
                    "was_self_corrected": False
                }

        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": error_message,
            "was_self_corrected": False
        }

    finally:
        cur.close()
        conn.close()