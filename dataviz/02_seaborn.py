# %% [markdown]
# # 02 — Seaborn
#
# Seaborn wraps Matplotlib with a higher-level API designed for statistical graphics.
# The main wins over raw Matplotlib:
#   - Beautiful defaults out of the box
#   - One-line statistical plots (box, violin, regression, pair plot, heatmap)
#   - Native understanding of tidy DataFrames (just pass column names as strings)
#
# Seaborn returns Matplotlib Axes objects, so you can still use `ax.set_title()` etc.
# to customise any chart.

# %%
import seaborn as sns
import matplotlib.pyplot as plt
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
df["month"] = df["date"].dt.to_period("M").astype(str)


# %% [markdown]
# ## 1. Themes

# %%
# Pick a theme once at the top of your script/notebook — affects all charts
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)

# Available styles: whitegrid, darkgrid, white, dark, ticks
# Available palettes: muted, deep, pastel, bright, dark, colorblind

# Reset to matplotlib defaults if needed
# sns.reset_defaults()


# %% [markdown]
# ## 2. Distribution — histogram + KDE

# %%
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

# Histogram
sns.histplot(data=df, x="revenue", bins=8, ax=axes[0], color="#2563EB")
axes[0].set_title("Revenue Distribution (histogram)")
axes[0].set_xlabel("Revenue (€)")

# KDE (Kernel Density Estimate) — smoothed distribution curve
sns.kdeplot(data=df, x="revenue", ax=axes[1], fill=True, color="#2563EB")
axes[1].set_title("Revenue Distribution (KDE)")
axes[1].set_xlabel("Revenue (€)")

plt.tight_layout()
plt.show()


# %% [markdown]
# ## 3. Distribution split by category

# %%
fig, ax = plt.subplots(figsize=(8, 4))

sns.histplot(
    data=df,
    x="revenue",
    hue="category",       # colour by category
    bins=6,
    kde=True,             # overlay KDE curve
    ax=ax,
)
ax.set_title("Revenue Distribution by Category")
plt.tight_layout()
plt.show()


# %% [markdown]
# ## 4. Bar chart — with confidence intervals

# %%
# seaborn barplot shows the mean + bootstrapped 95% CI by default
fig, ax = plt.subplots(figsize=(7, 4))

sns.barplot(data=df, x="customer", y="revenue", ax=ax, palette="muted")
ax.set_title("Average Revenue per Order by Customer")
ax.set_ylabel("Avg Revenue (€)")
plt.tight_layout()
plt.show()


# %% [markdown]
# ## 5. Count plot — frequency of a categorical variable

# %%
fig, ax = plt.subplots(figsize=(7, 4))

sns.countplot(data=df, x="product", order=df["product"].value_counts().index, ax=ax)
ax.set_title("Number of Orders by Product")
ax.set_ylabel("Order Count")
plt.tight_layout()
plt.show()


# %% [markdown]
# ## 6. Box plot — distribution + outliers per group

# %%
fig, ax = plt.subplots(figsize=(7, 4))

sns.boxplot(data=df, x="category", y="revenue", ax=ax, palette="muted")
ax.set_title("Revenue Distribution by Category (Box Plot)")
ax.set_ylabel("Revenue (€)")
plt.tight_layout()
plt.show()


# %% [markdown]
# ## 7. Violin plot — distribution shape per group

# %%
fig, ax = plt.subplots(figsize=(7, 4))

# inner="point" shows individual data points inside the violin
sns.violinplot(data=df, x="category", y="revenue", ax=ax, inner="point", palette="muted")
ax.set_title("Revenue Distribution by Category (Violin)")
plt.tight_layout()
plt.show()


# %% [markdown]
# ## 8. Strip / swarm plot — individual data points per group

# %%
fig, ax = plt.subplots(figsize=(7, 4))

# Overlay strip plot on a box plot for full picture
sns.boxplot(data=df, x="customer", y="revenue", ax=ax, palette="muted", width=0.5)
sns.stripplot(data=df, x="customer", y="revenue", ax=ax, color="black", size=5, alpha=0.6)

ax.set_title("Revenue per Order by Customer")
plt.tight_layout()
plt.show()


# %% [markdown]
# ## 9. Scatter plot with regression line

# %%
fig, ax = plt.subplots(figsize=(7, 5))

sns.regplot(
    data=df,
    x="quantity",
    y="revenue",
    ax=ax,
    scatter_kws={"alpha": 0.7, "s": 60},
    line_kws={"color": "#DC2626"},
)
ax.set_title("Quantity vs Revenue (with regression line)")
plt.tight_layout()
plt.show()


# %% [markdown]
# ## 10. Heatmap — correlation matrix

# %%
numeric_cols = ["quantity", "unit_price", "revenue"]
corr = df[numeric_cols].corr()

fig, ax = plt.subplots(figsize=(6, 5))

sns.heatmap(
    corr,
    annot=True,          # show correlation values in cells
    fmt=".2f",
    cmap="coolwarm",     # diverging colormap: blue = negative, red = positive
    vmin=-1, vmax=1,
    square=True,
    ax=ax,
)
ax.set_title("Correlation Matrix")
plt.tight_layout()
plt.show()


# %% [markdown]
# ## 11. Heatmap — aggregated pivot (e.g. revenue by customer × region)

# %%
pivot = df.pivot_table(values="revenue", index="customer", columns="region", aggfunc="sum", fill_value=0)

fig, ax = plt.subplots(figsize=(7, 4))

sns.heatmap(
    pivot,
    annot=True,
    fmt=".0f",
    cmap="YlOrRd",
    linewidths=0.5,
    ax=ax,
)
ax.set_title("Revenue by Customer × Region")
plt.tight_layout()
plt.show()


# %% [markdown]
# ## 12. Pair plot — pairwise relationships between all numeric columns

# %%
# Shows scatter plots for every pair of numeric columns + distributions on the diagonal
# Useful for a quick correlation overview during EDA
g = sns.pairplot(
    df[["quantity", "unit_price", "revenue", "category"]],
    hue="category",        # colour by category
    diag_kind="kde",       # KDE on diagonal
    plot_kws={"alpha": 0.6},
)
g.figure.suptitle("Pairwise Relationships", y=1.02)
plt.show()


# %% [markdown]
# ## 13. FacetGrid — same chart repeated per group (small multiples)

# %%
g = sns.FacetGrid(df, col="category", height=4, aspect=1.2)
g.map_dataframe(sns.barplot, x="customer", y="revenue")
g.set_axis_labels("Customer", "Revenue (€)")
g.set_titles(col_template="{col_name}")
g.figure.suptitle("Revenue by Customer, split by Category", y=1.04)
plt.show()
