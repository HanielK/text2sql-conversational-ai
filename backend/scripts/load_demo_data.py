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
            INSERT INTO customers (id, name, email, country) VALUES
            (1, 'Alice Johnson', 'alice@example.com', 'USA'),
            (2, 'Bob Smith', 'bob@example.com', 'USA'),
            (3, 'Charlie Brown', 'charlie@example.com', 'UK'),
            (4, 'Diana Prince', 'diana@example.com', 'Canada'),
            (5, 'Ethan Hunt', 'ethan@example.com', 'USA');
            """)

            # ----------------------------------
            # PRODUCTS
            # ----------------------------------
            cur.execute("""
            INSERT INTO products (id, name, category, price) VALUES
            (1, 'Laptop Pro', 'Electronics', 1200),
            (2, 'Wireless Mouse', 'Electronics', 50),
            (3, 'Office Chair', 'Furniture', 300),
            (4, 'Standing Desk', 'Furniture', 600),
            (5, 'Headphones', 'Electronics', 150);
            """)

            # ----------------------------------
            # ORDERS
            # ----------------------------------
            cur.execute("""
            INSERT INTO orders (id, customer_id, order_date, total_amount) VALUES
            (1, 1, '2024-01-01', 1250),
            (2, 2, '2024-01-05', 350),
            (3, 3, '2024-01-10', 300),
            (4, 1, '2024-02-01', 600),
            (5, 4, '2024-02-15', 750),
            (6, 5, '2024-03-01', 1350);
            """)

            # ----------------------------------
            # ORDER ITEMS
            # ----------------------------------
            cur.execute("""
            INSERT INTO order_items (id, order_id, product_id, quantity, price) VALUES
            (1, 1, 1, 1, 1200),
            (2, 1, 2, 1, 50),

            (3, 2, 3, 1, 300),
            (4, 2, 2, 1, 50),

            (5, 3, 3, 1, 300),

            (6, 4, 4, 1, 600),

            (7, 5, 4, 1, 600),
            (8, 5, 5, 1, 150),

            (9, 6, 1, 1, 1200),
            (10, 6, 5, 1, 150);
            """)

            # ----------------------------------
            # PAYMENTS
            # ----------------------------------
            cur.execute("""
            INSERT INTO payments (id, order_id, payment_method, amount, status) VALUES
            (1, 1, 'Credit Card', 1250, 'Completed'),
            (2, 2, 'PayPal', 350, 'Completed'),
            (3, 3, 'Credit Card', 300, 'Completed'),
            (4, 4, 'Bank Transfer', 600, 'Completed'),
            (5, 5, 'Credit Card', 750, 'Completed'),
            (6, 6, 'PayPal', 1350, 'Completed');
            """)

            # ----------------------------------
            # SHIPMENTS
            # ----------------------------------
            cur.execute("""
            INSERT INTO shipments (id, order_id, carrier, shipped_date, delivery_date, status) VALUES
            (1, 1, 'UPS', '2024-01-02', '2024-01-05', 'Delivered'),
            (2, 2, 'FedEx', '2024-01-06', '2024-01-09', 'Delivered'),
            (3, 3, 'DHL', '2024-01-11', '2024-01-15', 'Delivered'),
            (4, 4, 'UPS', '2024-02-02', '2024-02-06', 'Delivered'),
            (5, 5, 'FedEx', '2024-02-16', '2024-02-20', 'Delivered'),
            (6, 6, 'DHL', '2024-03-02', '2024-03-06', 'Delivered');
            """)

            print("✅ Demo data loaded successfully!")

if __name__ == "__main__":
    load_demo_data()