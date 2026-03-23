from backend.db import get_connection

def reset_demo():
    with get_connection() as conn:
        with conn.cursor() as cur:

            print("🧹 Resetting demo environment...")

            # ----------------------------------
            # Clear relational data (ORDER MATTERS)
            # Child tables FIRST → then parent tables
            # ----------------------------------
            cur.execute("TRUNCATE order_items RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE payments RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE shipments RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE orders RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE customers RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE products RESTART IDENTITY CASCADE;")

            print("✅ Cleared relational tables")

            # ----------------------------------
            # Clear embeddings (AI memory)
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
            # OPTIONAL (HIGHLY RECOMMENDED)
            # Reset feedback + golden queries if applicable
            # ----------------------------------
            RESET_GOLDEN = True  # 👈 TOGGLE THIS

            if RESET_GOLDEN:
                try:
                    cur.execute("DELETE FROM golden_queries;")
                    print("✅ Cleared golden queries")
                except Exception:
                    print("ℹ️ golden_queries table not found (skipping)")
            else:
                print("ℹ️ Keeping golden queries (production mode)")

            print("🎯 Demo environment FULLY reset.")

if __name__ == "__main__":
    reset_demo()