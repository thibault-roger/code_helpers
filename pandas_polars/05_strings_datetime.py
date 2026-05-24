# %% [markdown]
# # 05 — Strings & DateTime
#
# Common string manipulations and date/time operations.

# %%
import pandas as pd
import polars as pl
from datetime import date

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
# ## — Strings —

# %% [markdown]
# ## 1. Case transformation & stripping whitespace

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["customer"].str.upper()
df_pd["customer"].str.lower()
df_pd["customer"].str.title()
df_pd["customer"].str.strip()       # remove leading/trailing whitespace

# ── Polars ──────────────────────────────────────────────────────────────
df_pl["customer"].str.to_uppercase()
df_pl["customer"].str.to_lowercase()
df_pl["customer"].str.strip_chars()


# %% [markdown]
# ## 2. Contains, starts/ends with, count occurrences

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["product"].str.contains("op", case=False)    # case-insensitive
df_pd["product"].str.startswith("Mo")
df_pd["product"].str.endswith("ard")
df_pd["product"].str.count("o")

# ── Polars ──────────────────────────────────────────────────────────────
df_pl["product"].str.contains("op")
df_pl["product"].str.starts_with("Mo")
df_pl["product"].str.ends_with("ard")
df_pl["product"].str.count_matches("o")


# %% [markdown]
# ## 3. Replace & remove

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["product"].str.replace("Laptop", "Notebook", regex=False)
df_pd["region"].str.replace(r"^(North|South)", "NS", regex=True)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl["product"].str.replace("Laptop", "Notebook", literal=True)
df_pl["region"].str.replace(r"^(North|South)", "NS")


# %% [markdown]
# ## 4. Split and extract parts

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
# Split a "YYYY-MM-DD" string and grab the year
df_pd["date"].str.split("-").str[0]         # year as string

# Split into multiple columns
df_pd["date"].str.split("-", expand=True).rename(columns={0: "year", 1: "month", 2: "day"})

# ── Polars ──────────────────────────────────────────────────────────────
df_pl["date"].str.split("-").list.first()   # year as string

# Split into struct, then unnest to columns
df_pl.with_columns(
    pl.col("date").str.splitn("-", 3).alias("parts")
).unnest("parts")


# %% [markdown]
# ## 5. String length and padding

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["product"].str.len()
df_pd["order_id"].astype(str).str.zfill(6)     # "1001" → "001001"

# ── Polars ──────────────────────────────────────────────────────────────
df_pl["product"].str.len_chars()
df_pl["order_id"].cast(pl.Utf8).str.zfill(6)


# %% [markdown]
# ## 6. Regex extract

# %%
# Extract the first two letters of the product name
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["product"].str.extract(r"^([A-Za-z]{2})", expand=False)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl["product"].str.extract(r"^([A-Za-z]{2})", group_index=1)


# %% [markdown]
# ## — DateTime —

# %% [markdown]
# ## 7. Parse dates from strings

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["date"] = pd.to_datetime(df_pd["date"])          # auto-detect format
df_pd["date"] = pd.to_datetime(df_pd["date"], format="%Y-%m-%d")  # explicit

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = df_pl.with_columns(
    pl.col("date").str.to_date("%Y-%m-%d")
)


# %% [markdown]
# ## 8. Extract date components

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["year"]    = df_pd["date"].dt.year
df_pd["month"]   = df_pd["date"].dt.month
df_pd["day"]     = df_pd["date"].dt.day
df_pd["weekday"] = df_pd["date"].dt.day_name()    # "Monday", "Tuesday" …
df_pd["week"]    = df_pd["date"].dt.isocalendar().week

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = df_pl.with_columns(
    pl.col("date").dt.year().alias("year"),
    pl.col("date").dt.month().alias("month"),
    pl.col("date").dt.day().alias("day"),
    pl.col("date").dt.weekday().alias("weekday"),   # 1=Mon … 7=Sun
    pl.col("date").dt.week().alias("week"),
)


# %% [markdown]
# ## 9. Date arithmetic

# %%
import pandas as pd

# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["days_since_start"] = (df_pd["date"] - df_pd["date"].min()).dt.days
df_pd["next_week"] = df_pd["date"] + pd.Timedelta(days=7)

# ── Polars ──────────────────────────────────────────────────────────────
df_pl = df_pl.with_columns(
    (pl.col("date") - pl.col("date").min()).dt.total_days().alias("days_since_start"),
    (pl.col("date") + pl.duration(days=7)).alias("next_week"),
)


# %% [markdown]
# ## 10. Filter by date range

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd[df_pd["date"] >= "2024-02-01"]
df_pd[df_pd["date"].between("2024-02-01", "2024-03-31")]

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.filter(pl.col("date") >= date(2024, 2, 1))
df_pl.filter(pl.col("date").is_between(date(2024, 2, 1), date(2024, 3, 31)))


# %% [markdown]
# ## 11. Group by time period (month, quarter)

# %%
# ── Pandas ──────────────────────────────────────────────────────────────
df_pd["month_period"] = df_pd["date"].dt.to_period("M")
df_pd.groupby("month_period")["revenue"].sum()

# ── Polars ──────────────────────────────────────────────────────────────
df_pl.with_columns(
    pl.col("date").dt.truncate("1mo").alias("month_start")
).group_by("month_start").agg(
    pl.col("revenue").sum()
).sort("month_start")
