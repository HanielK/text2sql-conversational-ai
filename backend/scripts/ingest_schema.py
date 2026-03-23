from backend.embeddings import get_embedding
from backend.db import get_connection

def ingest_schema():

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Get tables
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)

            tables = cur.fetchall()

            for (table_name,) in tables:

                # Get columns
                cur.execute(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                """)

                columns = cur.fetchall()

                schema_text = f"Table {table_name} has columns: " + ", ".join(
                    [f"{col} ({dtype})" for col, dtype in columns]
                )

                embedding = get_embedding(schema_text)

                # Insert schema embedding
                cur.execute("""
                    INSERT INTO schema_embeddings (table_name, schema_text, embedding)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (table_name) DO UPDATE
                    SET schema_text = EXCLUDED.schema_text,
                        embedding = EXCLUDED.embedding
                """, (table_name, schema_text, embedding))

                # Insert column embeddings
                for col, dtype in columns:
                    col_text = f"{table_name}.{col} is a {dtype}"
                    col_embedding = get_embedding(col_text)

                    cur.execute("""
                        INSERT INTO column_embeddings (table_name, column_name, embedding)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (table_name, column_name) DO UPDATE
                        SET embedding = EXCLUDED.embedding
                    """, (table_name, col, col_embedding))

    print("✅ Schema ingestion complete")


if __name__ == "__main__":
    ingest_schema()