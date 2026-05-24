# %% [markdown]
# # 08 — I/O: Read & Write
#
# How to load and save data in CSV, Parquet, and Excel formats.
# Parquet is strongly preferred for any data you store and reload — it's
# faster, smaller, and preserves dtypes (including dates and nulls).

# %%
import pandas as pd
import polars as pl
import tempfile, os

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

# Use a temp directory so this script is runnable anywhere
TMP = tempfile.mkdtemp()


# %% [markdown]
# ## 1. CSV

# %%
csv_path = os.path.join(TMP, "sales.csv")

# ── Write ────────────────────────────────────────────────────────────────
# Pandas
df_pd.to_csv(csv_path, index=False)             # index=False: don't write row numbers

# Polars
df_pl.write_csv(csv_path)

# ── Read ─────────────────────────────────────────────────────────────────
# Pandas
df_pd = pd.read_csv(csv_path)
df_pd = pd.read_csv(csv_path,
    parse_dates=["date"],           # parse date column automatically
    dtype={"order_id": int},        # enforce a column dtype
    usecols=["order_id", "customer", "revenue"],  # load only specific columns
)

# Polars
df_pl = pl.read_csv(csv_path)
df_pl = pl.read_csv(csv_path,
    try_parse_dates=True,           # attempt to auto-parse date strings
    columns=["order_id", "customer", "revenue"],  # load only specific columns
)

# Polars lazy read (only loads data when .collect() is called — better for large files)
df_pl_lazy = pl.scan_csv(csv_path).filter(pl.col("revenue") > 500).collect()


# %% [markdown]
# ## 2. Parquet (recommended for stored data)
#
# - ~5–10x faster to read than CSV for large files
# - Compressed: typically 3–5x smaller than CSV
# - Preserves column types (dates, nulls, integers) — no type inference needed

# %%
parquet_path = os.path.join(TMP, "sales.parquet")

# ── Write ────────────────────────────────────────────────────────────────
# Pandas (requires pyarrow or fastparquet)
df_pd.to_parquet(parquet_path, index=False, compression="snappy")

# Polars
df_pl.write_parquet(parquet_path, compression="snappy")

# ── Read ─────────────────────────────────────────────────────────────────
# Pandas
df_pd = pd.read_parquet(parquet_path)
df_pd = pd.read_parquet(parquet_path, columns=["order_id", "customer", "revenue"])

# Polars
df_pl = pl.read_parquet(parquet_path)
df_pl = pl.read_parquet(parquet_path, columns=["order_id", "customer", "revenue"])

# Polars lazy read — Polars pushes column pruning and row filters into the file reader
df_pl_lazy = (
    pl.scan_parquet(parquet_path)
    .filter(pl.col("revenue") > 500)
    .select("customer", "product", "revenue")
    .collect()
)


# %% [markdown]
# ## 3. Excel

# %%
# pip install openpyxl  (for .xlsx)
excel_path = os.path.join(TMP, "sales.xlsx")

# ── Write ────────────────────────────────────────────────────────────────
# Pandas
df_pd.to_excel(excel_path, sheet_name="Sales", index=False)

# Write multiple sheets
with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
    df_pd.to_excel(writer, sheet_name="Sales", index=False)
    df_pd.groupby("category")[["revenue"]].sum().to_excel(writer, sheet_name="Summary")

# Polars (requires xlsx2csv + openpyxl for write)
df_pl.write_excel(excel_path, worksheet="Sales")

# ── Read ─────────────────────────────────────────────────────────────────
# Pandas
df_pd = pd.read_excel(excel_path, sheet_name="Sales")
df_pd = pd.read_excel(excel_path, sheet_name=0)        # by position

# Polars
df_pl = pl.read_excel(excel_path, sheet_name="Sales")


# %% [markdown]
# ## 4. Format comparison

# %%
# Rough guide (varies by data and machine):
#
# ┌──────────┬────────────┬────────┬───────────────┬──────────────────────────┐
# │ Format   │ File size  │ Speed  │ Dtype safety  │ Use when                 │
# ├──────────┼────────────┼────────┼───────────────┼──────────────────────────┤
# │ CSV      │ Large      │ Slow   │ None          │ Sharing with non-Python  │
# │ Parquet  │ Small      │ Fast   │ Full          │ Default for analysis      │
# │ Excel    │ Large      │ Slow   │ Partial       │ Sharing with stakeholders│
# └──────────┴────────────┴────────┴───────────────┴──────────────────────────┘
#
# Rule: use Parquet for everything you store and load in Python.
# Use CSV/Excel only at the edges (receiving external data, delivering to stakeholders).


# %% [markdown]
# ## 5. Convert between Pandas and Polars

# %%
# Pandas → Polars
df_pl = pl.from_pandas(df_pd)

# Polars → Pandas
df_pd = df_pl.to_pandas()

# Via Arrow (zero-copy when possible — faster for large DataFrames)
import pyarrow as pa
arrow_table = df_pl.to_arrow()
df_pd = arrow_table.to_pandas()
df_pl = pl.from_arrow(arrow_table)
