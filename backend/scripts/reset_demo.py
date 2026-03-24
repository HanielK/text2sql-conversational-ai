from backend.db import get_connection
from pathlib import Path
import shutil


def reset_demo():

    print("\n🧹 FULL DEMO RESET STARTED")
    print("=" * 50)

    # --------------------------------------------------
    # DB RESET
    # --------------------------------------------------
    with get_connection() as conn:
        with conn.cursor() as cur:

            print("🧹 Resetting database...")

            cur.execute("TRUNCATE order_items RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE payments RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE shipments RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE orders RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE customers RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE products RESTART IDENTITY CASCADE;")

            print("✅ Cleared relational tables")

            cur.execute("DELETE FROM schema_embeddings;")
            cur.execute("DELETE FROM column_embeddings;")
            cur.execute("DELETE FROM document_embeddings;")

            print("✅ Cleared embeddings")

            cur.execute("DELETE FROM query_logs;")
            cur.execute("DELETE FROM evaluation_metrics;")

            print("✅ Cleared logs & metrics")

    # --------------------------------------------------
    # FILE RESET (UPDATED — SAFE)
    # --------------------------------------------------
    BASE_DIR = Path(__file__).resolve().parents[2]

    feedback_dir = BASE_DIR / "data" / "feedback"
    golden_file = BASE_DIR / "data" / "golden_queries" / "golden_queries.json"
    # failures_file = BASE_DIR / "data" / "failures" / "failures.json" keep commented to preserve file history

    print("\n🧹 Resetting file-based memory...")

    # --------------------------------------------------
    # Clear feedback FILES ONLY (keep directory)
    # --------------------------------------------------
    feedback_dir.mkdir(parents=True, exist_ok=True)

    for file in feedback_dir.glob("*.json"):
        file.unlink()

    print("✅ Cleared feedback (files only)")

    # --------------------------------------------------
    # Clear golden queries
    # --------------------------------------------------
    golden_file.parent.mkdir(parents=True, exist_ok=True)
    golden_file.write_text("[]", encoding="utf-8")

    print("✅ Cleared golden queries")

    # --------------------------------------------------
    # Clear failures - keep commented to preserve file history
    # --------------------------------------------------
    # failures_file.parent.mkdir(parents=True, exist_ok=True)
    # failures_file.write_text("[]", encoding="utf-8")

    # print("✅ Cleared failures")

    print("\n🎯 DEMO RESET COMPLETE — CLEAN STATE READY")
    print("=" * 50)


if __name__ == "__main__":
    reset_demo()