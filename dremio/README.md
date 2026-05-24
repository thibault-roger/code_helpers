# Dremio — Data Read & Write in Python

## Connection options

| Method | Speed | Setup | Write support | Use when |
|--------|-------|-------|---------------|----------|
| **Arrow Flight** | Fast | Medium (port 32010) | Yes | Default — bulk reads/writes |
| **REST API** | Slower | Low (just HTTP) | Via SQL only | Quick scripts, no driver |
| SQLAlchemy/ODBC | Medium | High (ODBC driver) | Yes | Legacy integrations |

Arrow Flight is the native Dremio protocol. It transfers data in columnar format (Apache Arrow) with minimal overhead — the right default for any non-trivial volume.

## Files

| File | Description |
|------|-------------|
| [`client.py`](client.py) | Production `DremioClient` — Arrow Flight, parallel reads, batched writes, streaming |
| [`rest_client.py`](rest_client.py) | Lightweight REST API client — no driver required |
| [`requirements.txt`](requirements.txt) | Dependencies |

## Quick start

```python
from dremio.client import DremioClient, DremioConfig

cfg = DremioConfig(host="dremio.company.com", username="user", password="pass")
client = DremioClient(cfg)

# Read — parallel across Dremio fragments
df = client.read('SELECT col_a, col_b FROM "space"."table" WHERE dt >= \'2025-01\'')

# Stream — constant RAM, for datasets larger than memory
for chunk in client.stream('SELECT * FROM "space"."huge_table"'):
    process(chunk)

# Write — batched
client.write(df, "my_space/output_table")

# Stream directly to Parquet — never loads full dataset in RAM
client.stream_to_parquet('SELECT * FROM "space"."huge_table"', "/tmp/output.parquet")
```

## High-volume checklist

1. **Prune columns** — never `SELECT *` on wide tables
2. **Push predicates** — filter on partition keys in SQL, not in Python
3. **Use `stream()`** instead of `read()` when dataset > available RAM
4. **Use `stream_to_parquet()`** for large intermediate files
5. **Tune `batch_size`** and `max_workers` in `DremioConfig` for your cluster
