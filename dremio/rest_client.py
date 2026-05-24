"""
Dremio REST API client — no driver or special port required.

Trade-offs vs Arrow Flight:
- Slower: results are JSON, not columnar binary
- No native streaming: must paginate manually
- Write support is SQL-only (INSERT/CTAS), not bulk upload
- Simpler setup: just HTTPS to port 9047

Use this when Arrow Flight (port 32010) is not accessible, or for
lightweight scripts that don't need bulk performance.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import polars as pl
import requests


@dataclass
class DremioRestConfig:
    base_url: str          # e.g. "https://dremio.company.com:9047"
    username: str
    password: str
    poll_interval: float = 0.5
    page_size: int = 500   # max rows per results page (Dremio cap: 500)


class DremioRestClient:
    def __init__(self, cfg: DremioRestConfig) -> None:
        self.cfg = cfg
        self._session = requests.Session()
        self._authenticate()

    def _authenticate(self) -> None:
        resp = self._session.post(
            f"{self.cfg.base_url}/apiv2/login",
            json={"userName": self.cfg.username, "password": self.cfg.password},
        )
        resp.raise_for_status()
        token = resp.json()["token"]
        self._session.headers.update(
            {"Authorization": f"_dremio{token}", "Content-Type": "application/json"}
        )

    def _submit_job(self, sql: str) -> str:
        resp = self._session.post(
            f"{self.cfg.base_url}/api/v3/sql",
            json={"sql": sql},
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _wait_for_job(self, job_id: str) -> dict:
        terminal = {"COMPLETED", "FAILED", "CANCELED"}
        while True:
            resp = self._session.get(f"{self.cfg.base_url}/api/v3/job/{job_id}")
            resp.raise_for_status()
            status = resp.json()
            if status["jobState"] in terminal:
                return status
            time.sleep(self.cfg.poll_interval)

    def _fetch_all_pages(self, job_id: str, row_count: int) -> list[dict]:
        rows: list[dict] = []
        offset = 0
        while offset < row_count:
            resp = self._session.get(
                f"{self.cfg.base_url}/api/v3/job/{job_id}/results",
                params={"offset": offset, "limit": self.cfg.page_size},
            )
            resp.raise_for_status()
            page = resp.json()
            rows.extend(page["rows"])
            offset += self.cfg.page_size
        return rows

    def read(self, sql: str) -> pl.DataFrame:
        """
        Execute a SQL query and return all results as a Polars DataFrame.

        Automatically paginates through Dremio's result pages (max 500 rows
        per page). For large result sets, prefer Arrow Flight instead.
        """
        job_id = self._submit_job(sql)
        status = self._wait_for_job(job_id)

        if status["jobState"] != "COMPLETED":
            raise RuntimeError(
                f"Job {job_id} ended with state {status['jobState']}: "
                f"{status.get('errorMessage', 'no details')}"
            )

        row_count = status.get("rowCount", 0)
        if row_count == 0:
            return pl.DataFrame()

        rows = self._fetch_all_pages(job_id, row_count)
        return pl.DataFrame(rows)

    def execute(self, sql: str) -> None:
        """Execute a write/DDL statement (INSERT, CTAS, DROP, etc.)."""
        job_id = self._submit_job(sql)
        status = self._wait_for_job(job_id)
        if status["jobState"] != "COMPLETED":
            raise RuntimeError(
                f"Job {job_id} failed: {status.get('errorMessage', 'no details')}"
            )
