"""Shared fixtures for MCP server tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from glassflow_mcp.cluster import ClusterConnection, ClusterRegistry


class MockPipeline:
    """Minimal mock of glassflow.etl.Pipeline."""

    def __init__(self, pipeline_id: str = "test-pipeline", **kwargs: Any) -> None:
        self.pipeline_id = pipeline_id
        self._config = {
            "version": "v3",
            "pipeline_id": pipeline_id,
            "name": kwargs.get("name", "Test Pipeline"),
            "sources": [],
            "sink": {},
        }
        self._health = {
            "pipeline_id": pipeline_id,
            "overall_status": kwargs.get("status", "Running"),
        }
        self.dlq = MagicMock()
        self.dlq.state.return_value = {"messages": 0}

    def to_dict(self) -> dict:
        return self._config

    def health(self) -> dict:
        return self._health

    def resume(self) -> None:
        pass

    def update(self, patch: dict) -> None:
        self._config.update(patch)


class MockGlassFlowClient:
    """Mock of glassflow.etl.Client with controllable responses."""

    def __init__(self) -> None:
        self._pipelines: dict[str, MockPipeline] = {}

    def add_pipeline(self, pipeline_id: str, **kwargs: Any) -> MockPipeline:
        p = MockPipeline(pipeline_id, **kwargs)
        self._pipelines[pipeline_id] = p
        return p

    def list_pipelines(self) -> list[dict]:
        return [
            {
                "pipeline_id": p.pipeline_id,
                "name": p._config["name"],
                "status": p._health["overall_status"],
            }
            for p in self._pipelines.values()
        ]

    def get_pipeline(self, pipeline_id: str) -> MockPipeline:
        if pipeline_id not in self._pipelines:
            raise Exception(f"Pipeline '{pipeline_id}' not found")
        return self._pipelines[pipeline_id]

    def create_pipeline(self, pipeline_config: dict | None = None, **kwargs: Any) -> MockPipeline:
        if pipeline_config:
            pid = pipeline_config.get("pipeline_id", "new-pipeline")
            name = pipeline_config.get("name", pid)
        else:
            pid = "new-pipeline"
            name = pid
        return self.add_pipeline(pid, name=name)

    def stop_pipeline(self, pipeline_id: str) -> None:
        if pipeline_id not in self._pipelines:
            raise Exception(f"Pipeline '{pipeline_id}' not found")

    def delete_pipeline(self, pipeline_id: str) -> None:
        if pipeline_id not in self._pipelines:
            raise Exception(f"Pipeline '{pipeline_id}' not found")
        del self._pipelines[pipeline_id]

    def disable_usagestats(self) -> None:
        pass


class MockVMClient:
    """Mock VictoriaMetrics client."""

    def __init__(self) -> None:
        self._results: list[dict] = []

    def set_results(self, results: list[dict]) -> None:
        self._results = results

    def instant_query(self, query: str) -> list[dict]:
        return self._results

    def get_metric_value(self, query: str) -> float | None:
        if not self._results:
            return None
        return float(self._results[0]["value"][1])

    def healthy(self) -> bool:
        return True

    def close(self) -> None:
        pass


class MockVLClient:
    """Mock VictoriaLogs client."""

    def __init__(self) -> None:
        self._logs: list[dict] = []

    def set_logs(self, logs: list[dict]) -> None:
        self._logs = logs

    def query(self, query: str, limit: int = 50, **kwargs: Any) -> list[dict]:
        return self._logs[:limit]

    def healthy(self) -> bool:
        return True

    def close(self) -> None:
        pass


def make_registry(
    gf: MockGlassFlowClient | None = None,
    vm: MockVMClient | None = None,
    vl: MockVLClient | None = None,
) -> ClusterRegistry:
    """Create a ClusterRegistry with a pre-connected 'test' cluster."""
    gf = gf or MockGlassFlowClient()
    vm = vm or MockVMClient()
    vl = vl or MockVLClient()

    reg = ClusterRegistry()
    conn = ClusterConnection(
        name="test",
        api_url="http://test-api:8081",
        gf_client=gf,
        vm_client=vm,
        vl_client=vl,
    )
    reg._clusters["test"] = conn
    reg._active_name = "test"
    return reg


@pytest.fixture()
def registry() -> ClusterRegistry:
    return make_registry()
