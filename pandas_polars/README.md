# Data Manipulation with Pandas & Polars

A practical reference for analysts moving into Python. Every file is self-contained and runnable — open any one and go.

> **Tip:** Open these files in VS Code with the Python extension. Each `# %%` marker is an interactive cell you can run with `Shift+Enter`, just like a notebook.

---

## Pandas vs Polars — when to use which

| | Pandas | Polars |
|---|---|---|
| **Best for** | Ecosystem compatibility (sklearn, matplotlib, statsmodels) | Speed and large datasets |
| **Syntax style** | Imperative, index-heavy | Expressive, expression-based |
| **Performance** | Single-threaded by default | Multi-threaded, lazy evaluation |
| **Memory** | Higher (copies on many ops) | Lower (zero-copy Arrow backend) |
| **Null handling** | `NaN` (float) + `None` mixed | Explicit `null` everywhere |
| **Learning curve** | Gentler (more resources) | Steeper but more consistent |

**Rule of thumb:** start with Pandas. Switch to Polars (or use it alongside) when you hit performance or memory walls.

---

## Files

| File | Topics |
|------|--------|
| [`01_loading_exploring.py`](01_loading_exploring.py) | Create DataFrames, inspect shape/dtypes/stats, head/tail/sample |
| [`02_selecting_filtering.py`](02_selecting_filtering.py) | Select columns, filter rows, multiple conditions, `isin`, `between` |
| [`03_column_ops.py`](03_column_ops.py) | Add/rename/drop columns, type casting, apply functions |
| [`04_groupby_agg.py`](04_groupby_agg.py) | GroupBy, multiple aggregations, pivot tables, window/cumulative functions |
| [`05_strings_datetime.py`](05_strings_datetime.py) | String ops (contains/replace/split), date parsing, date arithmetic |
| [`06_joins_reshape.py`](06_joins_reshape.py) | Join types, concat, melt (wide→long), pivot (long→wide), sort |
| [`07_missing_data.py`](07_missing_data.py) | Detect nulls, drop, fill (constant / forward-fill / backward-fill) |
| [`08_io.py`](08_io.py) | Read/write CSV, Parquet, Excel |

---

## Sample dataset

All files use the same 12-row sales table so you can focus on the operations, not the data.

```
order_id | date       | customer | region | product  | category    | qty | unit_price | discount | revenue
---------|------------|----------|--------|----------|-------------|-----|------------|----------|--------
1001     | 2024-01-05 | Alice    | North  | Laptop   | Electronics | 1   | 999.0      | 0.10     | 899.1
1002     | 2024-01-12 | Bob      | South  | Mouse    | Accessories | 3   | 25.0       | 0.00     | 75.0
...
```

---

## Setup

```bash
pip install pandas polars openpyxl pyarrow
```
