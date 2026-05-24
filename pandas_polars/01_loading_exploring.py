# %% [markdown]
# # 01 — Loading & Exploring
#
# How to create DataFrames from common sources and get a first read on your data.

# %%
import pandas as pd
import polars as pl

# Shared sample data used throughout all files
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


# %% [markdown]
# ## 1. Creating DataFrames

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd = pd.DataFrame(SALES_DATA)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = pl.DataFrame(SALES_DATA)


# %% [markdown]
# ### From a list of dicts (common when loading JSON / API responses)

# %%
rows = [
    {"product": "Laptop", "price": 999.0},
    {"product": "Mouse",  "price": 25.0},
]

# ── Pandas ──────────────────────────────────────────────────────────────
pd.DataFrame(rows)

# ── Polars ──────────────────────────────────────────────────────────────
pl.DataFrame(rows)


# %% [markdown]
# ### From CSV / Parquet / Excel (see 08_io.py for full options)

# %%
# pd.read_csv("sales.csv")
# pd.read_parquet("sales.parquet")
# pd.read_excel("sales.xlsx", sheet_name="Sheet1")

# pl.read_csv("sales.csv")
# pl.read_parquet("sales.parquet")
# pl.read_excel("sales.xlsx")


# %% [markdown]
# ## 2. First look at the data

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
print(df_pd.head(3))       # first N rows
print(df_pd.tail(3))       # last N rows
print(df_pd.sample(3))     # random N rows

# ── Polars ──────────────────────────────────────────────────────────────
print(df_pl.head(3))
print(df_pl.tail(3))
print(df_pl.sample(3))


# %% [markdown]
# ## 3. Shape and column names

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
print(df_pd.shape)          # (rows, cols)
print(df_pd.columns.tolist())

# ── Polars ──────────────────────────────────────────────────────────────
print(df_pl.shape)
print(df_pl.columns)


# %% [markdown]
# ## 4. Data types

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
print(df_pd.dtypes)

# ── Polars ──────────────────────────────────────────────────────────────
print(df_pl.dtypes)         # list of Polars dtype objects
print(df_pl.schema)         # {column: dtype} dict — often more readable


# %% [markdown]
# ## 5. Summary statistics

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
print(df_pd.describe())             # numeric columns only by default
print(df_pd.describe(include="all")) # include object columns too

# ── Polars ──────────────────────────────────────────────────────────────
print(df_pl.describe())             # always includes all columns


# %% [markdown]
# ## 6. Null counts

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
print(df_pd.isnull().sum())         # nulls per column
print(df_pd.isnull().sum().sum())   # total nulls

# ── Polars ──────────────────────────────────────────────────────────────
print(df_pl.null_count())           # one-liner, returns a DataFrame


# %% [markdown]
# ## 7. Unique values and frequency counts

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
print(df_pd["customer"].nunique())          # number of distinct values
print(df_pd["customer"].unique())           # array of distinct values
print(df_pd["customer"].value_counts())     # frequency table

# ── Polars ──────────────────────────────────────────────────────────────
print(df_pl["customer"].n_unique())
print(df_pl["customer"].unique())
print(df_pl["customer"].value_counts(sort=True))


# %% [markdown]
# ## 8. Quick info summary (Pandas only)

# %%
# df.info() prints dtypes + non-null counts + memory usage in one shot
# Polars doesn't have a direct equivalent — use schema + null_count instead
df_pd.info()
