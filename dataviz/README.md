# Data Visualization

Three libraries, three levels of control — pick the right one for the job.

| Library | Best for | Output | Interactivity |
|---------|----------|--------|---------------|
| **Matplotlib** | Full control, publication figures, custom layouts | PNG / PDF | No |
| **Seaborn** | Statistical plots in one line, beautiful defaults | PNG / PDF | No |
| **Plotly** | Interactive charts, dashboards, sharing via HTML | HTML / PNG | Yes |

**Rule of thumb:**
- Exploring data → Seaborn or Plotly Express (fast, expressive)
- Presenting to stakeholders → Plotly (interactive HTML) or Seaborn (clean static)
- Full layout control / publication → Matplotlib

---

## Files

| File | Topics |
|------|--------|
| [`01_matplotlib.py`](01_matplotlib.py) | Figure/axes model, line, bar, scatter, histogram, subplots, saving |
| [`02_seaborn.py`](02_seaborn.py) | Themes, distributions, bar/box/violin, regression, heatmap, pairplot, facets |
| [`03_plotly.py`](03_plotly.py) | Plotly Express one-liners, Graph Objects, subplots, interactive HTML export |

All files use the same 12-row sales dataset — same as the `pandas_polars/` chapter.

## Setup

```bash
pip install matplotlib seaborn plotly pandas
```

> **VS Code tip:** each `# %%` marker is a runnable cell. Use the Python extension
> (`Shift+Enter`) to run cells interactively and see charts inline.
