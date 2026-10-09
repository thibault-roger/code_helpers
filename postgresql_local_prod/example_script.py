"""
example_script.py — a template for YOUR scripts. Copy it, rename it, change the SQL.

It runs unchanged against the local server or a remote database; the terminal
decides which, through DATABASE_URL:

    eval "$(make -s db-env)"                        # local
    python example_script.py

    set -a; source .env.prod; set +a                # remote (see docs/05_remote_database.md)
    python example_script.py

Explained step by step in docs/03_python_code.md.
"""

from __future__ import annotations

import polars as pl

from client import PostgresClient
from config import PgConfig


def main() -> None:
    # 1. Read the connection settings from the environment (never hard-code them)
    cfg = PgConfig.from_env()
    print(f"Connected to: {cfg.safe_url()}")  # password is masked

    # 2. Open the client; `with` closes the connections at the end, even on error
    with PostgresClient(cfg) as client:
        # 3. READ — values go in `params` (":since"), never pasted into the SQL string
        recent = client.read_polars(
            """
            SELECT customer_id, count(*) AS orders, sum(amount) AS revenue
            FROM sales_orders
            WHERE order_date >= :since
            GROUP BY customer_id
            ORDER BY revenue DESC
            LIMIT 5
            """,
            {"since": "2024-12-01"},
        )
        print(recent)

        # 4. WRITE — rows go into a table that a migration created.
        #    ON CONFLICT DO NOTHING makes the script safe to run twice.
        client.execute(
            """
            INSERT INTO customers (customer_id, full_name, email)
            VALUES (:id, :name, :email)
            ON CONFLICT (customer_id) DO NOTHING
            """,
            {"id": 900_001, "name": "Example Customer", "email": "example@example.com"},
        )

        # 5. Bulk write from a DataFrame (fast COPY, all-or-nothing)
        new_customers = pl.DataFrame(
            {
                "customer_id": [900_002, 900_003],
                "full_name": ["Ada", "Grace"],
                "email": [None, "grace@example.com"],
            }
        )
        # skip ids that already exist, so a second run doesn't hit the primary key
        existing_ids = client.read_polars(
            "SELECT customer_id FROM customers WHERE customer_id = ANY(:ids)",
            {"ids": new_customers["customer_id"].to_list()},
        )["customer_id"].to_list()
        to_insert = new_customers.filter(~pl.col("customer_id").is_in(existing_ids))
        print(f"Inserted {client.write_polars(to_insert, 'customers')} new customer(s)")


if __name__ == "__main__":
    main()
