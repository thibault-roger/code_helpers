# %% [markdown]
# # 02 — Selecting & Filtering
#
# How to pick the columns and rows you actually want.

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
# ## 1. Select columns

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["customer"]                               # Series (single column)
df_pd[["customer", "product", "revenue"]]       # DataFrame (multiple columns)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl["customer"]                               # Series
df_pl.select("customer")                        # DataFrame with one column
df_pl.select("customer", "product", "revenue")  # DataFrame with multiple columns

# Polars also accepts pl.col() expressions inside select — useful for patterns
df_pl.select(pl.col("^.*_price$"))              # all columns matching a regex


# %% [markdown]
# ## 2. Select rows by position

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd.iloc[0]           # first row as Series
df_pd.iloc[0:3]         # rows 0, 1, 2
df_pd.iloc[[0, 5, 9]]   # specific row indices

# ── Polars ──────────────────────────────────────────────────────────────
df_pl[0]                # first row as DataFrame
df_pl[0:3]              # rows 0, 1, 2
df_pl[[0, 5, 9]]        # specific row indices


# %% [markdown]
# ## 3. Filter rows — single condition

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd[df_pd["customer"] == "Alice"]
df_pd[df_pd["revenue"] > 500]

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.filter(pl.col("customer") == "Alice")
df_pl.filter(pl.col("revenue") > 500)


# %% [markdown]
# ## 4. Filter rows — multiple conditions

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
# Use & (AND), | (OR), ~ (NOT) — always wrap each condition in parentheses
df_pd[(df_pd["customer"] == "Alice") & (df_pd["revenue"] > 500)]
df_pd[(df_pd["region"] == "North") | (df_pd["region"] == "East")]
df_pd[~(df_pd["category"] == "Accessories")]   # NOT

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.filter((pl.col("customer") == "Alice") & (pl.col("revenue") > 500))
df_pl.filter((pl.col("region") == "North") | (pl.col("region") == "East"))
df_pl.filter(~(pl.col("category") == "Accessories"))


# %% [markdown]
# ## 5. isin — match a list of values

# %%
targets = ["Alice", "Charlie"]

# ── Pandas ──────────────────────────────────────────────────────────────
df_pd[df_pd["customer"].isin(targets)]

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.filter(pl.col("customer").is_in(targets))


# %% [markdown]
# ## 6. between — numeric or date range

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd[df_pd["revenue"].between(100, 700)]           # inclusive by default
df_pd[df_pd["unit_price"].between(50, 400)]

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.filter(pl.col("revenue").is_between(100, 700))
df_pl.filter(pl.col("unit_price").is_between(50, 400))


# %% [markdown]
# ## 7. String-based filter (contains / startswith / endswith)

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd[df_pd["product"].str.contains("top")]        # case-sensitive
df_pd[df_pd["product"].str.startswith("Mo")]
df_pd[df_pd["product"].str.endswith("ard")]

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.filter(pl.col("product").str.contains("top"))
df_pl.filter(pl.col("product").str.starts_with("Mo"))
df_pl.filter(pl.col("product").str.ends_with("ard"))


# %% [markdown]
# ## 8. Combining column selection with row filtering

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd.loc[df_pd["customer"] == "Alice", ["product", "revenue"]]

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.filter(pl.col("customer") == "Alice").select("product", "revenue")


# %% [markdown]
# ## 9. Pandas query() — SQL-like string syntax (quick exploration)

# %%
# Pandas only — handy for interactive exploration, avoid in production code
df_pd.query("customer == 'Alice' and revenue > 500")
df_pd.query("region in ['North', 'East'] and quantity >= 2")
