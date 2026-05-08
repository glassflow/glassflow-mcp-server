"""HTTP client wrapping the GlassFlow REST API."""

from __future__ import annotations

import httpx


class GlassFlowAPIError(Exception):
    """Raised when the GlassFlow API returns a non-success status code."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"GlassFlow API error {status_code}: {detail}")


class GlassFlowClient:
    """Thin wrapper around the GlassFlow REST API.

    All methods raise ``GlassFlowAPIError`` on non-2xx responses so callers
    can surface actionable error messages instead of raw stack traces.
    """

    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=30.0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
    ) -> httpx.Response:
        response = self._client.request(method, path, json=json)
        if not response.is_success:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise GlassFlowAPIError(response.status_code, str(detail))
        return response

    # ------------------------------------------------------------------
    # Pipeline CRUD
    # ------------------------------------------------------------------

    def list_pipelines(self) -> list[dict]:
        """GET /api/v1/pipeline — list all pipelines."""
        resp = self._request("GET", "/api/v1/pipeline")
        return resp.json()

    def get_pipeline(self, pipeline_id: str) -> dict:
        """GET /api/v1/pipeline/{id} — get full pipeline configuration."""
        resp = self._request("GET", f"/api/v1/pipeline/{pipeline_id}")
        return resp.json()

    def get_pipeline_health(self, pipeline_id: str) -> dict:
        """GET /api/v1/pipeline/{id}/health — get pipeline health/status."""
        resp = self._request("GET", f"/api/v1/pipeline/{pipeline_id}/health")
        return resp.json()

    def create_pipeline(self, config: dict) -> dict:
        """POST /api/v1/pipeline — create a new pipeline with V3 config."""
        resp = self._request("POST", "/api/v1/pipeline", json=config)
        return resp.json()

    def stop_pipeline(self, pipeline_id: str) -> None:
        """POST /api/v1/pipeline/{id}/stop — stop a running pipeline."""
        self._request("POST", f"/api/v1/pipeline/{pipeline_id}/stop")

    def resume_pipeline(self, pipeline_id: str) -> None:
        """POST /api/v1/pipeline/{id}/resume — resume a stopped pipeline."""
        self._request("POST", f"/api/v1/pipeline/{pipeline_id}/resume")

    def delete_pipeline(self, pipeline_id: str) -> None:
        """DELETE /api/v1/pipeline/{id} — delete a pipeline."""
        self._request("DELETE", f"/api/v1/pipeline/{pipeline_id}")

    def get_dlq_state(self, pipeline_id: str) -> dict:
        """GET /api/v1/pipeline/{id}/dlq/state — get dead-letter queue state."""
        resp = self._request(
            "GET", f"/api/v1/pipeline/{pipeline_id}/dlq/state"
        )
        return resp.json()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._client.close()
