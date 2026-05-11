"""VictoriaMetrics query client (PromQL)."""

from __future__ import annotations

from typing import Any

import httpx


class VMClient:
    """Query VictoriaMetrics via the Prometheus-compatible HTTP API."""

    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def instant_query(self, query: str) -> list[dict[str, Any]]:
        """Run a PromQL instant query and return the result vector."""
        resp = self._client.get("/api/v1/query", params={"query": query})
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "success":
            raise RuntimeError(f"VM query failed: {body}")
        return body["data"]["result"]

    def range_query(
        self,
        query: str,
        start: str,
        end: str,
        step: str = "60s",
    ) -> list[dict[str, Any]]:
        """Run a PromQL range query and return the result matrix."""
        resp = self._client.get(
            "/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "step": step},
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "success":
            raise RuntimeError(f"VM range query failed: {body}")
        return body["data"]["result"]

    def get_metric_value(self, query: str) -> float | None:
        """Run an instant query and return the scalar value (or None)."""
        results = self.instant_query(query)
        if not results:
            return None
        # [timestamp, value]
        return float(results[0]["value"][1])

    def healthy(self) -> bool:
        try:
            resp = self._client.get("/health")
            return resp.is_success
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        self._client.close()
