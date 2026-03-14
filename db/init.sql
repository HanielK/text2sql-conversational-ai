CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE schema_vectors (
    id SERIAL PRIMARY KEY,
    table_name TEXT,
    content TEXT,
    embedding VECTOR(1536)
);

CREATE TABLE query_logs (
    id SERIAL PRIMARY KEY,
    question TEXT,
    generated_sql TEXT,
    execution_time FLOAT,
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INT,
    order_date DATE,
    total_amount NUMERIC
);

INSERT INTO orders (customer_id, order_date, total_amount) VALUES
(1, '2024-01-01', 200),
(2, '2024-01-02', 150),
(3, '2024-01-03', 400),
(1, '2024-02-01', 500);