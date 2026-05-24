# %% [markdown]
# # 04 — GroupBy & Aggregations
#
# Summarize data by group: counts, sums, averages, and more.
# Also covers window/cumulative functions and pivot tables.

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
# ## 1. Simple aggregation

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd.groupby("customer")["revenue"].sum()
df_pd.groupby("customer")["revenue"].mean()
df_pd.groupby("customer")["order_id"].count()

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.group_by("customer").agg(pl.col("revenue").sum())
df_pl.group_by("customer").agg(pl.col("revenue").mean())
df_pl.group_by("customer").agg(pl.col("order_id").count())


# %% [markdown]
# ## 2. Multiple aggregations in one pass

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd.groupby("customer").agg(
    total_revenue=("revenue", "sum"),
    avg_revenue=("revenue", "mean"),
    order_count=("order_id", "count"),
    total_qty=("quantity", "sum"),
)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.group_by("customer").agg(
    pl.col("revenue").sum().alias("total_revenue"),
    pl.col("revenue").mean().alias("avg_revenue"),
    pl.col("order_id").count().alias("order_count"),
    pl.col("quantity").sum().alias("total_qty"),
)


# %% [markdown]
# ## 3. Group by multiple keys

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd.groupby(["customer", "category"]).agg(
    total_revenue=("revenue", "sum"),
    order_count=("order_id", "count"),
).reset_index()

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.group_by("customer", "category").agg(
    pl.col("revenue").sum().alias("total_revenue"),
    pl.col("order_id").count().alias("order_count"),
)


# %% [markdown]
# ## 4. Common aggregation functions

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd.groupby("category")["revenue"].agg(["sum", "mean", "min", "max", "std", "count"])

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.group_by("category").agg(
    pl.col("revenue").sum().alias("sum"),
    pl.col("revenue").mean().alias("mean"),
    pl.col("revenue").min().alias("min"),
    pl.col("revenue").max().alias("max"),
    pl.col("revenue").std().alias("std"),
    pl.col("revenue").count().alias("count"),
)


# %% [markdown]
# ## 5. Window functions — add group-level stats back to each row
#
# Unlike groupby (which collapses rows), window functions keep the original
# row count and add an aggregated value per group alongside each row.

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
# transform() applies the aggregation and broadcasts back to the original index
df_pd["customer_total"] = df_pd.groupby("customer")["revenue"].transform("sum")
df_pd["customer_share"] = df_pd["revenue"] / df_pd["customer_total"]

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = df_pl.with_columns(
    pl.col("revenue").sum().over("customer").alias("customer_total"),
    (pl.col("revenue") / pl.col("revenue").sum().over("customer")).alias("customer_share"),
)


# %% [markdown]
# ## 6. Cumulative / running aggregations

# %%
# Sort first so the running total is meaningful
df_pd_sorted = df_pd.sort_values("date")
df_pl_sorted = df_pl.sort("date")

# ── Pandas ──────────────────────────────────────────────────────────────
df_pd_sorted["running_revenue"] = df_pd_sorted["revenue"].cumsum()
df_pd_sorted["running_revenue_per_customer"] = (
    df_pd_sorted.groupby("customer")["revenue"].cumsum()
)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl_sorted = df_pl_sorted.with_columns(
    pl.col("revenue").cum_sum().alias("running_revenue"),
    pl.col("revenue").cum_sum().over("customer").alias("running_revenue_per_customer"),
)


# %% [markdown]
# ## 7. Rank within group

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["rank_in_customer"] = (
    df_pd.groupby("customer")["revenue"]
    .rank(method="dense", ascending=False)
    .astype(int)
)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = df_pl.with_columns(
    pl.col("revenue")
    .rank(method="dense", descending=True)
    .over("customer")
    .alias("rank_in_customer")
)


# %% [markdown]
# ## 8. Pivot table
#
# Rows = customer, Columns = region, Values = total revenue

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
pivot_pd = df_pd.pivot_table(
    values="revenue",
    index="customer",
    columns="region",
    aggfunc="sum",
    fill_value=0,
)
print(pivot_pd)

# ── Polars ──────────────────────────────────────────────────────────────
pivot_pl = df_pl.pivot(
    values="revenue",
    index="customer",
    columns="region",
    aggregate_function="sum",
)
print(pivot_pl)
