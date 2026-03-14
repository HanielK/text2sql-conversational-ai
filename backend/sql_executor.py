import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def execute_sql(sql: str):
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
            "error": None
        }

    except Exception as e:
        conn.rollback()
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": str(e)
        }

    finally:
        cur.close()
        conn.close()