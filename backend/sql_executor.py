import os
import psycopg
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# ---------------------------------------------------------
# Load environment variables from project root
# ---------------------------------------------------------

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------
# LLM SQL repair helper
# ---------------------------------------------------------

def repair_sql(original_sql: str, error_message: str):

    prompt = f"""
You are a PostgreSQL expert.

The following SQL query failed.

SQL:
{original_sql}

Error message:
{error_message}

Return a corrected PostgreSQL SQL query only.
Do not include explanation.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    fixed_sql = response.output_text.strip()

    return fixed_sql


# ---------------------------------------------------------
# Execute SQL with optional self-healing
# ---------------------------------------------------------

def execute_sql(sql: str, allow_repair: bool = True):

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
        # Attempt automatic SQL repair
        # -------------------------------------------------

        if allow_repair:

            try:

                fixed_sql = repair_sql(sql, error_message)

                print("Attempting SQL self-repair...")
                print("Original SQL:", sql)
                print("Repaired SQL:", fixed_sql)

                return execute_sql(fixed_sql, allow_repair=False)

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