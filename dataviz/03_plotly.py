# %% [markdown]
# # 03 — Plotly
#
# Plotly produces interactive charts: hover tooltips, zoom, pan, toggle legend items.
# Charts render directly in the browser or in VS Code / Jupyter.
#
# Two APIs — pick the right level:
#   plotly.express (px)  — one-liner charts from a DataFrame, fast to write
#   plotly.graph_objects (go) — full control over every element, more verbose
#
# Rule: start with px. Drop down to go only when you need something px can't do.

# %%
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

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

# Aggregated views
monthly     = df.resample("ME", on="date")["revenue"].sum().reset_index()
by_customer = df.groupby("customer")["revenue"].sum().reset_index()
by_product  = df.groupby("product")[["revenue", "quantity"]].sum().reset_index()
by_cat_cust = df.groupby(["customer", "category"])["revenue"].sum().reset_index()


# %% [markdown]
# ## — Plotly Express (px) — one-liners —

# %% [markdown]
# ## 1. Line chart

# %%
fig = px.line(
    monthly,
    x="date",
    y="revenue",
    title="Monthly Revenue",
    markers=True,
    labels={"revenue": "Revenue (€)", "date": "Month"},
    template="plotly_white",
)
fig.show()


# %% [markdown]
# ## 2. Bar chart — vertical

# %%
fig = px.bar(
    by_customer,
    x="customer",
    y="revenue",
    title="Total Revenue by Customer",
    color="customer",
    labels={"revenue": "Revenue (€)", "customer": ""},
    text_auto=",.0f",          # show formatted values on bars
    template="plotly_white",
)
fig.update_traces(textposition="outside")
fig.show()


# %% [markdown]
# ## 3. Bar chart — grouped (customer × category)

# %%
fig = px.bar(
    by_cat_cust,
    x="customer",
    y="revenue",
    color="category",
    barmode="group",           # side-by-side; use "stack" for stacked bars
    title="Revenue by Customer and Category",
    labels={"revenue": "Revenue (€)"},
    template="plotly_white",
)
fig.show()


# %% [markdown]
# ## 4. Horizontal bar chart

# %%
fig = px.bar(
    by_product.sort_values("revenue"),
    x="revenue",
    y="product",
    orientation="h",
    title="Revenue by Product",
    labels={"revenue": "Revenue (€)", "product": ""},
    template="plotly_white",
    color="revenue",
    color_continuous_scale="Blues",
)
fig.show()


# %% [markdown]
# ## 5. Scatter plot

# %%
fig = px.scatter(
    df,
    x="quantity",
    y="revenue",
    color="category",
    size="unit_price",         # bubble size = price
    hover_data=["product", "customer", "order_id"],   # extra info in tooltip
    title="Quantity vs Revenue",
    labels={"revenue": "Revenue (€)", "quantity": "Quantity"},
    template="plotly_white",
    trendline="ols",           # add regression line (requires statsmodels)
)
fig.show()


# %% [markdown]
# ## 6. Histogram

# %%
fig = px.histogram(
    df,
    x="revenue",
    nbins=8,
    color="category",
    barmode="overlay",
    opacity=0.7,
    title="Revenue Distribution by Category",
    labels={"revenue": "Revenue (€)"},
    template="plotly_white",
)
fig.show()


# %% [markdown]
# ## 7. Box plot

# %%
fig = px.box(
    df,
    x="customer",
    y="revenue",
    color="customer",
    points="all",              # show individual data points alongside the box
    title="Revenue Distribution by Customer",
    labels={"revenue": "Revenue (€)"},
    template="plotly_white",
)
fig.show()


# %% [markdown]
# ## 8. Pie / donut chart

# %%
fig = px.pie(
    by_customer,
    names="customer",
    values="revenue",
    title="Revenue Share by Customer",
    hole=0.4,                  # hole=0 → pie, hole>0 → donut
    template="plotly_white",
)
fig.update_traces(textposition="inside", textinfo="percent+label")
fig.show()


# %% [markdown]
# ## 9. Heatmap — pivot table

# %%
pivot = df.pivot_table(
    values="revenue",
    index="customer",
    columns="region",
    aggfunc="sum",
    fill_value=0,
)

fig = px.imshow(
    pivot,
    text_auto=",.0f",
    color_continuous_scale="Blues",
    title="Revenue by Customer × Region",
    labels={"color": "Revenue (€)"},
    aspect="auto",
)
fig.show()


# %% [markdown]
# ## 10. Facet — same chart per group (small multiples)

# %%
fig = px.bar(
    df,
    x="product",
    y="revenue",
    facet_col="customer",      # one column per customer
    color="category",
    title="Revenue by Product, per Customer",
    labels={"revenue": "Revenue (€)"},
    template="plotly_white",
)
fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))  # clean facet titles
fig.show()


# %% [markdown]
# ## — Plotly Graph Objects (go) — full control —

# %% [markdown]
# ## 11. Manually build a figure with go

# %%
fig = go.Figure()

fig.add_trace(go.Bar(
    x=by_customer["customer"],
    y=by_customer["revenue"],
    name="Revenue",
    marker_color=["#2563EB", "#16A34A", "#DC2626"],
    text=[f"€{r:,.0f}" for r in by_customer["revenue"]],
    textposition="outside",
))

fig.update_layout(
    title="Total Revenue by Customer",
    xaxis_title="Customer",
    yaxis_title="Revenue (€)",
    yaxis_tickprefix="€",
    template="plotly_white",
    showlegend=False,
)
fig.show()


# %% [markdown]
# ## 12. Multiple chart types in one figure (make_subplots)

# %%
fig = make_subplots(
    rows=1, cols=2,
    subplot_titles=["Monthly Revenue (line)", "Revenue by Customer (bar)"],
)

# Left: line chart
fig.add_trace(
    go.Scatter(
        x=monthly["date"],
        y=monthly["revenue"],
        mode="lines+markers",
        name="Revenue",
        line=dict(color="#2563EB", width=2),
    ),
    row=1, col=1,
)

# Right: bar chart
fig.add_trace(
    go.Bar(
        x=by_customer["customer"],
        y=by_customer["revenue"],
        name="Customer revenue",
        marker_color=["#2563EB", "#16A34A", "#DC2626"],
    ),
    row=1, col=2,
)

fig.update_layout(
    title_text="Sales Overview",
    template="plotly_white",
    showlegend=False,
    height=400,
)
fig.show()


# %% [markdown]
# ## 13. Customise hover tooltip

# %%
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df["quantity"],
    y=df["revenue"],
    mode="markers",
    marker=dict(size=10, color=df["unit_price"], colorscale="Blues", showscale=True),
    customdata=df[["product", "customer", "order_id"]].values,
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "Customer: %{customdata[1]}<br>"
        "Order #%{customdata[2]}<br>"
        "Qty: %{x}<br>"
        "Revenue: €%{y:,.2f}<extra></extra>"
    ),
))

fig.update_layout(
    title="Quantity vs Revenue (custom tooltip)",
    xaxis_title="Quantity",
    yaxis_title="Revenue (€)",
    template="plotly_white",
)
fig.show()


# %% [markdown]
# ## 14. Export — save as interactive HTML or static image

# %%
fig = px.bar(by_customer, x="customer", y="revenue", title="Revenue by Customer")

# Interactive HTML — share with stakeholders, no Python needed to open
fig.write_html("/tmp/revenue.html")

# Static image — requires kaleido: pip install kaleido
# fig.write_image("/tmp/revenue.png", width=800, height=400, scale=2)
# fig.write_image("/tmp/revenue.pdf")


# %% [markdown]
# ## 15. Global layout defaults — apply once, affects all charts

# %%
# Set a default template so you don't repeat template= on every chart
import plotly.io as pio
pio.templates.default = "plotly_white"

# Override specific defaults
fig.update_layout(
    font_family="Arial",
    title_font_size=16,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
