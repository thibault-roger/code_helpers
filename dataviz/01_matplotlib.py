# %% [markdown]
# # 01 — Matplotlib
#
# Matplotlib is the foundation of Python data visualization. Every other library
# (Seaborn, Pandas .plot()) is built on top of it.
#
# Key mental model:
#   Figure  = the entire canvas (the window or saved file)
#   Axes    = one individual chart inside the Figure
#   Artist  = everything drawn on an Axes (lines, bars, text, …)
#
# Always use the object-oriented API: `fig, ax = plt.subplots()`
# Avoid the implicit `plt.plot()` style — it breaks the moment you have
# more than one chart.

# %%
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import numpy as np

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
    "revenue":    [899.1, 75.0, 142.5, 849.15, 700.0, 112.5, 225.0, 799.2, 665.0, 100.0, 899.1, 665.0],
}

df = pd.DataFrame(SALES_DATA)
df["date"] = pd.to_datetime(df["date"])

# Aggregated views used across examples
monthly   = df.resample("ME", on="date")["revenue"].sum().reset_index()
by_customer = df.groupby("customer")["revenue"].sum().reset_index()
by_product  = df.groupby("product")["revenue"].sum().sort_values(ascending=False).reset_index()


# %% [markdown]
# ## 1. The Figure / Axes model

# %%
fig, ax = plt.subplots(figsize=(8, 4))   # figsize in inches

ax.set_title("Chart title")
ax.set_xlabel("X axis label")
ax.set_ylabel("Y axis label")

plt.tight_layout()   # prevent labels from being clipped
plt.show()


# %% [markdown]
# ## 2. Line chart — time series

# %%
fig, ax = plt.subplots(figsize=(9, 4))

ax.plot(
    monthly["date"],
    monthly["revenue"],
    marker="o",         # show a dot at each data point
    linewidth=2,
    color="#2563EB",
    label="Monthly revenue",
)

ax.set_title("Monthly Revenue", fontsize=14, fontweight="bold")
ax.set_xlabel("Month")
ax.set_ylabel("Revenue (€)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
ax.legend()
ax.grid(axis="y", linestyle="--", alpha=0.5)

plt.tight_layout()
plt.show()


# %% [markdown]
# ## 3. Vertical bar chart — compare categories

# %%
fig, ax = plt.subplots(figsize=(7, 4))

bars = ax.bar(
    by_customer["customer"],
    by_customer["revenue"],
    color=["#2563EB", "#16A34A", "#DC2626"],
    width=0.5,
)

# Add value labels on top of each bar
ax.bar_label(bars, fmt="€%.0f", padding=4, fontsize=10)

ax.set_title("Total Revenue by Customer", fontsize=14, fontweight="bold")
ax.set_xlabel("Customer")
ax.set_ylabel("Revenue (€)")
ax.set_ylim(0, by_customer["revenue"].max() * 1.2)   # room for labels
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
ax.grid(axis="y", linestyle="--", alpha=0.4)
ax.spines[["top", "right"]].set_visible(False)       # remove chart border clutter

plt.tight_layout()
plt.show()


# %% [markdown]
# ## 4. Horizontal bar chart — better for long category names

# %%
fig, ax = plt.subplots(figsize=(7, 4))

ax.barh(
    by_product["product"],
    by_product["revenue"],
    color="#2563EB",
)

ax.set_title("Revenue by Product", fontsize=14, fontweight="bold")
ax.set_xlabel("Revenue (€)")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
ax.invert_yaxis()   # highest revenue at the top
ax.spines[["top", "right"]].set_visible(False)

plt.tight_layout()
plt.show()


# %% [markdown]
# ## 5. Scatter plot — correlation between two numeric variables

# %%
fig, ax = plt.subplots(figsize=(7, 5))

# Map categories to colors
colors = {"Electronics": "#2563EB", "Accessories": "#16A34A"}
for category, group in df.groupby("category"):
    ax.scatter(
        group["quantity"],
        group["revenue"],
        label=category,
        color=colors[category],
        s=80,           # marker size
        alpha=0.8,
        edgecolors="white",
        linewidths=0.5,
    )

ax.set_title("Quantity vs Revenue by Category", fontsize=14, fontweight="bold")
ax.set_xlabel("Quantity")
ax.set_ylabel("Revenue (€)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
ax.legend(title="Category")
ax.grid(linestyle="--", alpha=0.4)
ax.spines[["top", "right"]].set_visible(False)

plt.tight_layout()
plt.show()


# %% [markdown]
# ## 6. Histogram — distribution of a numeric variable

# %%
fig, ax = plt.subplots(figsize=(7, 4))

ax.hist(df["revenue"], bins=8, color="#2563EB", edgecolor="white", linewidth=0.8)

ax.set_title("Revenue Distribution", fontsize=14, fontweight="bold")
ax.set_xlabel("Revenue (€)")
ax.set_ylabel("Count")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
ax.spines[["top", "right"]].set_visible(False)

plt.tight_layout()
plt.show()


# %% [markdown]
# ## 7. Subplots — multiple charts in one figure

# %%
fig, axes = plt.subplots(1, 2, figsize=(12, 4))   # 1 row, 2 columns

# Left: revenue by customer
axes[0].bar(by_customer["customer"], by_customer["revenue"], color="#2563EB")
axes[0].set_title("Revenue by Customer")
axes[0].set_ylabel("Revenue (€)")
axes[0].spines[["top", "right"]].set_visible(False)

# Right: revenue by product (horizontal)
axes[1].barh(by_product["product"], by_product["revenue"], color="#16A34A")
axes[1].set_title("Revenue by Product")
axes[1].set_xlabel("Revenue (€)")
axes[1].invert_yaxis()
axes[1].spines[["top", "right"]].set_visible(False)

fig.suptitle("Sales Summary", fontsize=15, fontweight="bold", y=1.02)
plt.tight_layout()
plt.show()


# %% [markdown]
# ## 8. Grouped bar chart — compare two metrics side by side

# %%
by_cat_cust = (
    df.groupby(["customer", "category"])["revenue"]
    .sum()
    .unstack(fill_value=0)
)

customers = by_cat_cust.index.tolist()
categories = by_cat_cust.columns.tolist()
x = np.arange(len(customers))
width = 0.35
colors_map = {"Electronics": "#2563EB", "Accessories": "#16A34A"}

fig, ax = plt.subplots(figsize=(8, 4))

for i, cat in enumerate(categories):
    offset = (i - len(categories) / 2 + 0.5) * width
    bars = ax.bar(x + offset, by_cat_cust[cat], width, label=cat, color=colors_map[cat])

ax.set_title("Revenue by Customer & Category", fontsize=14, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(customers)
ax.set_ylabel("Revenue (€)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
ax.legend(title="Category")
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
plt.show()


# %% [markdown]
# ## 9. Style and theme

# %%
# Built-in styles — pick one and use it consistently
print(plt.style.available[:10])    # list first 10

# Apply a style globally for the session
plt.style.use("seaborn-v0_8-whitegrid")

# Or use a context manager for a single block
with plt.style.context("ggplot"):
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [4, 5, 6])
    plt.show()


# %% [markdown]
# ## 10. Save a figure

# %%
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(by_customer["customer"], by_customer["revenue"])
ax.set_title("Revenue by Customer")

fig.savefig("/tmp/revenue_by_customer.png", dpi=150, bbox_inches="tight")
fig.savefig("/tmp/revenue_by_customer.pdf", bbox_inches="tight")   # vector — best for reports

plt.close(fig)   # free memory when saving without displaying
