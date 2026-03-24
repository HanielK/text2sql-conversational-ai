from backend.db import get_connection


def load_demo_data():
    with get_connection() as conn:
        with conn.cursor() as cur:

            print("🧹 Clearing existing demo data...")

            # ----------------------------------
            # Clear tables (ORDER MATTERS)
            # ----------------------------------
            cur.execute("TRUNCATE order_items RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE payments RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE shipments RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE orders RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE customers RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE products RESTART IDENTITY CASCADE;")

            print("📦 Loading demo data...")

            # ----------------------------------
            # CUSTOMERS
            # ----------------------------------
            cur.execute("""
            INSERT INTO customers (name, email, country, signup_date) VALUES
            ('Alice Johnson', 'alice@example.com', 'USA', '2023-12-01'),
            ('Bob Smith', 'bob@example.com', 'USA', '2023-12-05'),
            ('Charlie Brown', 'charlie@example.com', 'UK', '2023-12-10'),
            ('Diana Prince', 'diana@example.com', 'Canada', '2023-12-15'),
            ('Ethan Hunt', 'ethan@example.com', 'USA', '2023-12-20');
            """)

            # ----------------------------------
            # PRODUCTS
            # ----------------------------------
            cur.execute("""
            INSERT INTO products (name, category, price) VALUES
            ('Laptop Pro', 'Electronics', 1200),
            ('Wireless Mouse', 'Electronics', 50),
            ('Office Chair', 'Furniture', 300),
            ('Standing Desk', 'Furniture', 600),
            ('Headphones', 'Electronics', 150);
            """)

            # ----------------------------------
            # ORDERS
            # ----------------------------------
            cur.execute("""
            INSERT INTO orders (customer_id, order_date, status, total_amount) VALUES
            (1, '2024-01-01', 'Completed', 1250),
            (2, '2024-01-05', 'Completed', 350),
            (3, '2024-01-10', 'Completed', 300),
            (1, '2024-02-01', 'Completed', 600),
            (4, '2024-02-15', 'Completed', 750),
            (5, '2024-03-01', 'Completed', 1350);
            """)

            # ----------------------------------
            # ORDER ITEMS
            # ----------------------------------
            cur.execute("""
            INSERT INTO order_items (order_id, product_id, quantity, price) VALUES
            (1, 1, 1, 1200),
            (1, 2, 1, 50),

            (2, 3, 1, 300),
            (2, 2, 1, 50),

            (3, 3, 1, 300),

            (4, 4, 1, 600),

            (5, 4, 1, 600),
            (5, 5, 1, 150),

            (6, 1, 1, 1200),
            (6, 5, 1, 150);
            """)

            # ----------------------------------
            # PAYMENTS
            # ----------------------------------
            cur.execute("""
            INSERT INTO payments (order_id, payment_method, payment_date, amount) VALUES
            (1, 'Credit Card', '2024-01-01', 1250),
            (2, 'PayPal', '2024-01-05', 350),
            (3, 'Credit Card', '2024-01-10', 300),
            (4, 'Bank Transfer', '2024-02-01', 600),
            (5, 'Credit Card', '2024-02-15', 750),
            (6, 'PayPal', '2024-03-01', 1350);
            """)

            # ----------------------------------
            # SHIPMENTS
            # ----------------------------------
            cur.execute("""
            INSERT INTO shipments (order_id, shipped_date, delivery_date, carrier) VALUES
            (1, '2024-01-02', '2024-01-05', 'UPS'),
            (2, '2024-01-06', '2024-01-09', 'FedEx'),
            (3, '2024-01-11', '2024-01-15', 'DHL'),
            (4, '2024-02-02', '2024-02-06', 'UPS'),
            (5, '2024-02-16', '2024-02-20', 'FedEx'),
            (6, '2024-03-02', '2024-03-06', 'DHL');
            """)

            print("✅ Demo data loaded successfully!")


if __name__ == "__main__":
    load_demo_data()