from backend.db import get_connection
from pathlib import Path
import json


# --------------------------------------------------
# 🔥 MODE CONTROL
# --------------------------------------------------
PRO_MODE = False
# False = FULL RESET (demo mode)
# True  = KEEP learning data (prod mode)


def reset_demo():
    with get_connection() as conn:
        with conn.cursor() as cur:

            print("🧹 Resetting environment...")

            # ----------------------------------
            # Clear relational data
            # ----------------------------------
            cur.execute("TRUNCATE order_items RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE payments RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE shipments RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE orders RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE customers RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE products RESTART IDENTITY CASCADE;")

            print("✅ Cleared relational tables")

            # ----------------------------------
            # Clear embeddings
            # ----------------------------------
            cur.execute("DELETE FROM schema_embeddings;")
            cur.execute("DELETE FROM column_embeddings;")
            cur.execute("DELETE FROM document_embeddings;")

            print("✅ Cleared embeddings")

            # ----------------------------------
            # Clear logs / evaluation
            # ----------------------------------
            cur.execute("DELETE FROM query_logs;")
            cur.execute("DELETE FROM evaluation_metrics;")

            print("✅ Cleared logs & metrics")

            # ----------------------------------
            # FILE STORAGE CONTROL (🔥 PRO MODE)
            # ----------------------------------

            BASE_DIR = Path(__file__).resolve().parents[1]
            DATA_DIR = BASE_DIR / "data"

            feedback_file = DATA_DIR / "feedback" / "feedback.json"
            golden_file = DATA_DIR / "golden_queries" / "golden_queries.json"

            if PRO_MODE:
                print("🟢 PRO MODE ENABLED → Preserving learning data")
                print("   - feedback.json KEPT")
                print("   - golden_queries.json KEPT")

            else:
                print("🧪 DEMO MODE → Resetting learning data")

                # ---- Reset Feedback ----
                if feedback_file.exists():
                    with open(feedback_file, "w", encoding="utf-8") as f:
                        json.dump([], f)
                    print("✅ Cleared feedback.json")
                else:
                    print("ℹ️ feedback.json not found")

                # ---- Reset Golden Queries ----
                if golden_file.exists():
                    with open(golden_file, "w", encoding="utf-8") as f:
                        json.dump([], f)
                    print("✅ Cleared golden_queries.json")
                else:
                    print("ℹ️ golden_queries.json not found")

            print("🎯 Environment reset complete.")


if __name__ == "__main__":
    reset_demo()