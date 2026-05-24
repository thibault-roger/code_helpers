# %% [markdown]
# # 07 — Missing Data
#
# Detect, remove, and fill null values.
# The last two rows in the sample data have intentional nulls.

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
    "discount":   [0.10, 0.00, 0.05, 0.15, 0.00, 0.10, 0.00, 0.20, 0.05, 0.00, 0.10, None],  # 1 null
    "revenue":    [899.1, 75.0, 142.5, 849.15, 700.0, 112.5, 225.0, 799.2, 665.0, 100.0, 899.1, None],  # 1 null
}

df_pd = pd.DataFrame(SALES_DATA)
df_pl = pl.DataFrame(SALES_DATA)


# %% [markdown]
# ## 1. Detect nulls

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd.isnull()                  # boolean mask, same shape as df
df_pd.isnull().sum()            # null count per column
df_pd["revenue"].isnull()       # boolean Series for one column

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.null_count()                          # null count per column (as DataFrame)
df_pl["revenue"].is_null()                  # boolean Series
df_pl.filter(pl.col("revenue").is_null())   # rows where revenue is null


# %% [markdown]
# ## 2. Find rows with any null

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd[df_pd.isnull().any(axis=1)]

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.filter(
    pl.any_horizontal(pl.all().is_null())
)


# %% [markdown]
# ## 3. Drop rows with nulls

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd.dropna()                          # drop any row with at least one null
df_pd.dropna(subset=["revenue"])        # drop only when "revenue" is null
df_pd.dropna(thresh=9)                  # keep rows with at least 9 non-null values

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.drop_nulls()                      # drop any row with at least one null
df_pl.drop_nulls(subset=["revenue"])    # drop only when "revenue" is null


# %% [markdown]
# ## 4. Fill nulls with a constant

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["revenue"].fillna(0)
df_pd["discount"].fillna(0.0)
df_pd.fillna({"revenue": 0, "discount": 0.0})   # different values per column

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.with_columns(
    pl.col("revenue").fill_null(0),
    pl.col("discount").fill_null(0.0),
)


# %% [markdown]
# ## 5. Fill nulls with a derived value (mean, median)

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
revenue_mean = df_pd["revenue"].mean()
df_pd["revenue"].fillna(revenue_mean)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.with_columns(
    pl.col("revenue").fill_null(pl.col("revenue").mean())
)


# %% [markdown]
# ## 6. Forward fill and backward fill
#
# Useful for time-series data where you want to carry the last known value forward.

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["revenue"].ffill()    # forward fill (propagate last valid value)
df_pd["revenue"].bfill()    # backward fill (propagate next valid value)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.with_columns(
    pl.col("revenue").forward_fill().alias("revenue_ffill"),
    pl.col("revenue").backward_fill().alias("revenue_bfill"),
)


# %% [markdown]
# ## 7. Null-safe arithmetic
#
# In Pandas, NaN propagates through most operations (NaN + 1 = NaN).
# In Polars, null also propagates but you can override this.

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
# sum() ignores NaN by default; mean() also ignores NaN
df_pd["revenue"].sum()          # nulls excluded
df_pd["revenue"].mean()         # nulls excluded

# Explicit: to include nulls (propagate), use skipna=False
df_pd["revenue"].sum(skipna=False)      # returns NaN if any null

# ── Polars ──────────────────────────────────────────────────────────────
# Polars also ignores nulls in agg functions by default
df_pl["revenue"].sum()          # nulls excluded
df_pl["revenue"].mean()         # nulls excluded


# %% [markdown]
# ## 8. Replace specific sentinel values with null
#
# Common when importing data where -1, 0, or 999 means "unknown".

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["revenue"].replace(-1, None)
df_pd["revenue"].replace({-1: None, 0: None})

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.with_columns(
    pl.when(pl.col("revenue") == -1)
    .then(None)
    .otherwise(pl.col("revenue"))
    .alias("revenue")
)
