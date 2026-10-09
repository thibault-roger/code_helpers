"""
End-to-end demo — the same script runs locally and against production.

Prerequisites (local):
    python local_server.py start
    eval "$(python local_server.py env)"
    make migrate-apply          # tables come from Atlas, not from this script

Then:
    python demo.py

What it shows
-------------
1. Config comes only from the environment (config.py).
2. The schema version applied by Atlas is visible from the app.
3. Bulk load with COPY, read back with Polars/pandas, stream in batches.
4. Real PostgreSQL constraints (FK, CHECK) are enforced locally, exactly as in
   prod — something SQLite/DuckDB stand-ins would not reproduce faithfully.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl
from psycopg.errors import IntegrityError

from client import PostgresClient
from config import PgConfig

N_CUSTOMERS = 1_000
N_ORDERS = 200_000


def synthetic_data(seed: int = 42) -> tuple[pl.DataFrame, pl.DataFrame]:
    rng = np.random.default_rng(seed)
    customers = pl.DataFrame(
        {
            "customer_id": np.arange(1, N_CUSTOMERS + 1, dtype=np.int32),
            "full_name": [f"Customer {i}" for i in range(1, N_CUSTOMERS + 1)],
            "email": [f"customer{i}@example.com" for i in range(1, N_CUSTOMERS + 1)],
        }
    )  # created_at omitted -> DEFAULT now() from the migration

    order_dates = pl.date_range(dt.date(2024, 1, 1), dt.date(2024, 12, 31), eager=True)
    orders = pl.DataFrame(
        {
            "order_id": np.arange(1, N_ORDERS + 1, dtype=np.int64),
            "customer_id": rng.integers(1, N_CUSTOMERS + 1, N_ORDERS, dtype=np.int32),
            "order_date": order_dates.sample(
                N_ORDERS, with_replacement=True, seed=seed
            ),
            "amount": rng.uniform(5, 500, N_ORDERS).round(2),
            "status": rng.choice(["pending", "shipped", "cancelled"], N_ORDERS),
            "is_international": rng.random(N_ORDERS) < 0.15,
        }
    ).with_columns(pl.col("amount").cast(pl.Decimal(10, 2)))
    return customers, orders


def main() -> None:
    cfg = PgConfig.from_env()
    print(f"APP_ENV={cfg.app_env}  ->  {cfg.safe_url()}")

    with PostgresClient(cfg) as client:
        version = client.read_polars(
            "SELECT version, description FROM atlas_schema_revisions.atlas_schema_revisions"
            " ORDER BY version DESC LIMIT 1"
        )
        print(f"Schema version (Atlas): {version.row(0)}")

        if cfg.is_prod:
            print("APP_ENV=prod: skipping the destructive part of the demo.")
            return

        # Start from empty tables (local only!)
        client.execute("TRUNCATE sales_orders, customers")

        customers, orders = synthetic_data()
        client.write_polars(customers, "customers")
        client.write_polars(orders, "sales_orders")
        print(
            f"Loaded {customers.height:,} customers and {orders.height:,} orders via COPY"
        )

        # Aggregation runs in PostgreSQL; only the small result travels to Python
        monthly = client.read_polars(
            """
            SELECT date_trunc('month', order_date)::date AS month,
                   count(*)                              AS orders,
                   sum(amount)                           AS revenue
            FROM sales_orders
            WHERE status <> :excluded
            GROUP BY 1
            ORDER BY 1
            """,
            {"excluded": "cancelled"},
        )
        print(monthly.head(3))

        top = client.read_pandas(
            "SELECT c.full_name, sum(o.amount) AS revenue"
            " FROM sales_orders o JOIN customers c USING (customer_id)"
            " GROUP BY 1 ORDER BY 2 DESC LIMIT 3"
        )
        print(top)

        # Server-side cursor: RAM bounded by batch_size, not table size
        streamed = sum(
            b.height for b in client.stream_polars("SELECT * FROM sales_orders")
        )
        assert streamed == orders.height, (streamed, orders.height)
        print(f"Streamed {streamed:,} rows in batches of {cfg.read_chunksize:,}")

        # Constraints from the migration are enforced by the real engine
        bad = orders.head(1).with_columns(
            order_id=pl.lit(N_ORDERS + 1, pl.Int64),
            customer_id=pl.lit(999_999, pl.Int32),
        )
        try:
            client.write_polars(bad, "sales_orders")
        except IntegrityError as exc:
            print(f"Rejected as expected: {exc.diag.constraint_name}")


if __name__ == "__main__":
    main()
