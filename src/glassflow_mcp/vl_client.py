"""VictoriaLogs query client (LogsQL)."""

from __future__ import annotations

import json
from typing import Any

import httpx


class VLClient:
    """Query VictoriaLogs via the HTTP API."""

    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def query(
        self,
        query: str,
        limit: int = 50,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a LogsQL query and return matching log lines.

        Results are returned newest-first.
        """
        params: dict[str, Any] = {"query": query, "limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        resp = self._client.get("/select/logsql/query", params=params)
        resp.raise_for_status()

        # VL returns newline-delimited JSON (NDJSON)
        lines = []
        for line in resp.text.strip().split("\n"):
            if line:
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return lines

    def healthy(self) -> bool:
        try:
            resp = self._client.get("/health")
            return resp.is_success
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        self._client.close()
