# Environment Helpers — Poetry

Poetry manages two things at once: **dependencies** (what packages you need)
and **virtual environments** (an isolated Python install for each project).
Everything lives in `pyproject.toml` (your intent) and `poetry.lock` (the exact
resolved versions — always commit this file).

---

## Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Verify:

```bash
poetry --version
```

---

## Recommended one-time config

```bash
# Create the .venv folder inside the project directory (easier to find, works with VS Code)
poetry config virtualenvs.in-project true
```

---

## Start a new project

```bash
# Option A — new project from scratch (creates the folder + boilerplate)
poetry new my-project
cd my-project

# Option B — add poetry to an existing folder
cd my-project
poetry init          # interactive wizard
# or non-interactively:
poetry init --no-interaction --name my-project --python ">=3.11,<4.0"
```

---

## Daily workflow — quick reference

| Task | Command |
|------|---------|
| Add a package | `poetry add pandas` |
| Add multiple packages | `poetry add pandas polars plotly pyarrow` |
| Add a dev-only package | `poetry add --group dev ruff black pytest` |
| Remove a package | `poetry remove pandas` |
| Install all deps (from lockfile) | `poetry install` |
| Install without dev deps | `poetry install --without dev` |
| Update all packages | `poetry update` |
| Update one package | `poetry update pandas` |
| Show installed packages | `poetry show` |
| Show a package's details | `poetry show pandas` |
| Show dependency tree | `poetry show --tree` |
| Run a script in the venv | `poetry run python script.py` |
| Activate the venv in shell | `poetry shell` |
| Deactivate | `exit` |
| Where is the venv? | `poetry env info --path` |
| Python version in use | `poetry env info` |
| Export to requirements.txt | `poetry export -f requirements.txt --output requirements.txt --without-hashes` |
| Check for outdated packages | `poetry show --outdated` |
| Lock without installing | `poetry lock` |

---

## Dependency groups

Groups let you separate production deps from dev tools, notebook packages, etc.
Only the `[tool.poetry.dependencies]` group is installed by default in production.

```bash
# Add to a named group
poetry add --group dev     ruff black mypy pytest pytest-cov
poetry add --group notebook jupyterlab ipykernel ipywidgets

# Install everything including all groups
poetry install --with dev,notebook

# Install only main deps (e.g. in a Docker image)
poetry install --without dev,notebook
```

In `pyproject.toml` this looks like:

```toml
[tool.poetry.dependencies]
python = ">=3.11,<4.0"
pandas = ">=2.0"
polars = ">=0.20"

[tool.poetry.group.dev.dependencies]
ruff = "*"
black = "*"
pytest = "*"

[tool.poetry.group.notebook.dependencies]
jupyterlab = "*"
ipykernel = "*"
```

---

## Python version management

```bash
# Use a specific Python version for a project
poetry env use python3.11
poetry env use python3.12

# List available envs for this project
poetry env list

# Delete an env and start fresh
poetry env remove python3.11
poetry install
```

> If the Python version you need isn't on your machine, install it first with
> [pyenv](https://github.com/pyenv/pyenv):
> ```bash
> pyenv install 3.11
> pyenv local 3.11      # sets .python-version in the project folder
> poetry env use $(pyenv which python)
> ```

---

## Onboarding to an existing project

```bash
git clone https://github.com/org/project.git
cd project
poetry install          # reads poetry.lock, installs exact versions
poetry shell            # activate
```

---

## Version constraints cheatsheet

| Syntax | Meaning |
|--------|---------|
| `">=2.0"` | 2.0 or higher |
| `"^2.0"` | >=2.0 and <3.0 (caret — most common) |
| `"~2.1"` | >=2.1 and <2.2 (tilde — patch updates only) |
| `"*"` | Any version |
| `">=2.0,<3.0"` | Explicit range |

Prefer `^` for most packages — it allows minor updates but prevents breaking major version changes.

---

## Export for pip / Docker

```bash
# Generate requirements.txt from the lockfile
poetry export \
  -f requirements.txt \
  --output requirements.txt \
  --without dev,notebook \
  --without-hashes

# In a Dockerfile:
# COPY requirements.txt .
# RUN pip install -r requirements.txt
```

---

## Troubleshooting

**`poetry install` fails with solver conflicts**
```bash
poetry update                  # let the solver re-resolve everything
poetry add package@latest      # force latest version of a specific package
```

**Wrong Python version being used**
```bash
poetry env info                # check what's active
poetry env use python3.11      # switch
```

**VS Code doesn't see the venv**
```bash
poetry env info --path         # copy this path
# In VS Code: Ctrl+Shift+P → "Python: Select Interpreter" → paste path + /bin/python
```
With `virtualenvs.in-project = true`, VS Code auto-detects `.venv/` in the project root.

**Start fresh**
```bash
poetry env remove --all        # delete all envs for this project
rm poetry.lock                 # optional: re-resolve from scratch
poetry install
```
