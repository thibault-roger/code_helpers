# %% [markdown]
# # 06 — Joins & Reshaping
#
# Combine DataFrames (join/merge), stack them vertically (concat),
# and reshape between wide and long formats (pivot / melt).

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

# A secondary reference table (customer metadata)
customers_pd = pd.DataFrame({
    "customer": ["Alice", "Bob", "Charlie", "Diana"],
    "tier":     ["Gold", "Silver", "Gold", "Bronze"],
    "country":  ["FR", "DE", "FR", "UK"],
})
customers_pl = pl.DataFrame({
    "customer": ["Alice", "Bob", "Charlie", "Diana"],
    "tier":     ["Gold", "Silver", "Gold", "Bronze"],
    "country":  ["FR", "DE", "FR", "UK"],
})


# %% [markdown]
# ## 1. Join types
#
# ```
# inner  — only rows with a match in both tables
# left   — all rows from the left, nulls where no match in right
# right  — all rows from the right, nulls where no match in left
# outer  — all rows from both, nulls where no match on either side
# ```

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
pd.merge(df_pd, customers_pd, on="customer", how="inner")
pd.merge(df_pd, customers_pd, on="customer", how="left")   # keeps all orders
pd.merge(df_pd, customers_pd, on="customer", how="outer")  # keeps Diana (no orders)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.join(customers_pl, on="customer", how="inner")
df_pl.join(customers_pl, on="customer", how="left")
df_pl.join(customers_pl, on="customer", how="full")         # Polars uses "full" not "outer"


# %% [markdown]
# ## 2. Join on multiple keys

# %%
# Suppose we have a pricing table keyed on (product, region)
pricing_pd = pd.DataFrame({
    "product": ["Laptop", "Mouse"],
    "region":  ["North", "South"],
    "special_price": [879.0, 22.0],
})
pricing_pl = pl.DataFrame({
    "product": ["Laptop", "Mouse"],
    "region":  ["North", "South"],
    "special_price": [879.0, 22.0],
})

# ── Pandas ──────────────────────────────────────────────────────────────
pd.merge(df_pd, pricing_pd, on=["product", "region"], how="left")

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.join(pricing_pl, on=["product", "region"], how="left")


# %% [markdown]
# ## 3. Join on keys with different column names

# %%
# If left table has "customer" and right table has "client"
customers_renamed = customers_pd.rename(columns={"customer": "client"})
customers_renamed_pl = customers_pl.rename({"customer": "client"})

# ── Pandas ──────────────────────────────────────────────────────────────
pd.merge(df_pd, customers_renamed, left_on="customer", right_on="client", how="left")

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.join(customers_renamed_pl, left_on="customer", right_on="client", how="left")


# %% [markdown]
# ## 4. Concat — stack DataFrames vertically

# %%
first_half  = df_pd[df_pd["date"] < "2024-04-01"]
second_half = df_pd[df_pd["date"] >= "2024-04-01"]

# ── Pandas ──────────────────────────────────────────────────────────────
pd.concat([first_half, second_half], ignore_index=True)

# ── Polars ──────────────────────────────────────────────────────────────
first_half_pl  = df_pl.filter(pl.col("date") < "2024-04-01")
second_half_pl = df_pl.filter(pl.col("date") >= "2024-04-01")
pl.concat([first_half_pl, second_half_pl])


# %% [markdown]
# ## 5. Sort

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd.sort_values("revenue", ascending=False)
df_pd.sort_values(["customer", "revenue"], ascending=[True, False])

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.sort("revenue", descending=True)
df_pl.sort(["customer", "revenue"], descending=[False, True])


# %% [markdown]
# ## 6. Melt — wide to long
#
# Useful when you have one column per metric and need a single "metric" column.

# %%
# Wide format: one column per metric
wide_pd = pd.DataFrame({
    "customer": ["Alice", "Bob", "Charlie"],
    "jan_revenue": [1041.6, 775.0, 849.15],
    "feb_revenue": [112.5, 700.0, 225.0],
    "mar_revenue": [665.0, 0.0, 0.0],
})
wide_pl = pl.DataFrame({
    "customer": ["Alice", "Bob", "Charlie"],
    "jan_revenue": [1041.6, 775.0, 849.15],
    "feb_revenue": [112.5, 700.0, 225.0],
    "mar_revenue": [665.0, 0.0, 0.0],
})

# ── Pandas ──────────────────────────────────────────────────────────────
# id_vars: columns to keep as-is
# value_vars: columns to melt into rows
long_pd = wide_pd.melt(
    id_vars="customer",
    value_vars=["jan_revenue", "feb_revenue", "mar_revenue"],
    var_name="month",
    value_name="revenue",
)
print(long_pd)

# ── Polars ──────────────────────────────────────────────────────────────
long_pl = wide_pl.unpivot(
    index="customer",
    on=["jan_revenue", "feb_revenue", "mar_revenue"],
    variable_name="month",
    value_name="revenue",
)
print(long_pl)


# %% [markdown]
# ## 7. Pivot — long to wide
#
# Inverse of melt: turn category values into column names.

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
wide_back_pd = long_pd.pivot(index="customer", columns="month", values="revenue")
wide_back_pd.columns.name = None       # remove the "month" label on columns
wide_back_pd = wide_back_pd.reset_index()

# ── Polars ──────────────────────────────────────────────────────────────
wide_back_pl = long_pl.pivot(
    index="customer",
    columns="month",
    values="revenue",
    aggregate_function="first",
)
