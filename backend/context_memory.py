import os
import psycopg
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")


def get_last_result(session_id):

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT result_json
                FROM query_logs
                WHERE session_id = %s
                AND success = true
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id,)
            )

            row = cur.fetchone()

            if not row:
                return None

            return row[0]