# %% [markdown]
# # 03 — Column Operations
#
# Add, rename, drop, cast, and transform columns.

# %%
import pandas as pd
import polars as pl

SALES_DATA = {
    "order_id":   [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010, 1011, 1012],
    "date":       ["2024-01-05", "2024-01-12", "2024-01-20", "2024-02-03", "2024-02-15",
                   "2024-02-20", "2024-03-08", "2024-03-15", "2024-03-25", "2024-04-01",
                   "2024-04-22", "2024-05-10"],
    "customer":   ["Alice", "Bob", "Alice", "Charlie", "Bob", "Alice", "Charlie", "Bob",
                   "Alice", "Charlie", "Bob", "Alice"],
    "region":     ["North", "South", "North", "East", "South", "East", "North", "South",
                   "East", "North", "South", "East"],
    "product":    ["Laptop", "Mouse", "Keyboard", "Laptop", "Monitor", "Mouse", "Keyboard",
                   "Laptop", "Monitor", "Mouse", "Laptop", "Monitor"],
    "category":   ["Electronics", "Accessories", "Accessories", "Electronics", "Electronics",
                   "Accessories", "Accessories", "Electronics", "Electronics", "Accessories",
                   "Electronics", "Electronics"],
    "quantity":   [1, 3, 2, 1, 2, 5, 3, 1, 2, 4, 1, 2],
    "unit_price": [999.0, 25.0, 75.0, 999.0, 350.0, 25.0, 75.0, 999.0, 350.0, 25.0, 999.0, 350.0],
    "discount":   [0.10, 0.00, 0.05, 0.15, 0.00, 0.10, 0.00, 0.20, 0.05, 0.00, 0.10, None],
    "revenue":    [899.1, 75.0, 142.5, 849.15, 700.0, 112.5, 225.0, 799.2, 665.0, 100.0, 899.1, None],
}

df_pd = pd.DataFrame(SALES_DATA)
df_pl = pl.DataFrame(SALES_DATA)


# %% [markdown]
# ## 1. Add a new column

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["gross_revenue"] = df_pd["quantity"] * df_pd["unit_price"]
df_pd["is_discounted"] = df_pd["discount"] > 0

# ── Polars ──────────────────────────────────────────────────────────────
# with_columns() returns a new DataFrame — Polars DataFrames are immutable
df_pl = df_pl.with_columns(
    (pl.col("quantity") * pl.col("unit_price")).alias("gross_revenue"),
    (pl.col("discount") > 0).alias("is_discounted"),
)


# %% [markdown]
# ## 2. Add multiple columns at once

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd = df_pd.assign(
    revenue_per_unit=df_pd["revenue"] / df_pd["quantity"],
    discount_pct=df_pd["discount"] * 100,
)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = df_pl.with_columns(
    (pl.col("revenue") / pl.col("quantity")).alias("revenue_per_unit"),
    (pl.col("discount") * 100).alias("discount_pct"),
)


# %% [markdown]
# ## 3. Rename columns

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd = df_pd.rename(columns={"unit_price": "price", "order_id": "id"})

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = df_pl.rename({"unit_price": "price", "order_id": "id"})


# %% [markdown]
# ## 4. Drop columns

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd.drop(columns=["gross_revenue", "is_discounted"])
# In-place (avoid when possible — mutating DataFrames silently is a common bug source):
# df_pd.drop(columns=["gross_revenue"], inplace=True)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.drop("gross_revenue", "is_discounted")


# %% [markdown]
# ## 5. Reorder columns

# %%
cols = ["id", "date", "customer", "region", "product", "category",
        "quantity", "price", "discount", "revenue"]

# ── Pandas ──────────────────────────────────────────────────────────────
df_pd = df_pd[cols]

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = df_pl.select(cols)


# %% [markdown]
# ## 6. Type casting

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["quantity"] = df_pd["quantity"].astype(float)
df_pd["id"] = df_pd["id"].astype(str)
df_pd["date"] = pd.to_datetime(df_pd["date"])       # string → datetime

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = df_pl.with_columns(
    pl.col("quantity").cast(pl.Float64),
    pl.col("id").cast(pl.Utf8),
    pl.col("date").str.to_date(),                   # string → Date
)


# %% [markdown]
# ## 7. Apply a custom function row by row
#
# **Important:** avoid apply/map_elements on large data — they're slow because
# they break out of vectorized execution. Prefer built-in expressions first.

# %%
def label_revenue(rev):
    if rev is None:
        return "unknown"
    if rev >= 700:
        return "high"
    if rev >= 200:
        return "medium"
    return "low"

# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["revenue_label"] = df_pd["revenue"].apply(label_revenue)

# ── Polars ──────────────────────────────────────────────────────────────
# map_elements applies a Python function element-wise (slow but flexible)
df_pl = df_pl.with_columns(
    pl.col("revenue").map_elements(label_revenue, return_dtype=pl.Utf8).alias("revenue_label")
)


# %% [markdown]
# ## 8. Conditional column — if/elif/else equivalent (fast, vectorized)
#
# Prefer this over apply when you can express the logic as conditions.

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
import numpy as np
df_pd["revenue_label"] = np.where(
    df_pd["revenue"] >= 700, "high",
    np.where(df_pd["revenue"] >= 200, "medium", "low")
)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = df_pl.with_columns(
    pl.when(pl.col("revenue") >= 700).then(pl.lit("high"))
      .when(pl.col("revenue") >= 200).then(pl.lit("medium"))
      .otherwise(pl.lit("low"))
      .alias("revenue_label")
)
