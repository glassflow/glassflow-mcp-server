"""Tests for server factory and tool registration."""

from __future__ import annotations

from glassflow_mcp.server import create_server
from tests.conftest import MockGlassFlowClient, MockVLClient, MockVMClient


class TestCreateServer:
    def test_creates_mcp_instance(self):
        mcp = create_server(MockGlassFlowClient(), MockVMClient(), MockVLClient(), port=0)
        assert mcp is not None
        assert mcp.name == "GlassFlow Pipeline Manager"

    def test_registers_all_tools(self):
        mcp = create_server(MockGlassFlowClient(), MockVMClient(), MockVLClient(), port=0)
        tool_names = {t.name for t in mcp._tool_manager._tools.values()}
        expected = {
            "list_pipelines",
            "get_pipeline",
            "get_pipeline_health",
            "create_pipeline",
            "stop_pipeline",
            "resume_pipeline",
            "edit_pipeline",
            "delete_pipeline",
            "get_dlq_state",
            "query_pipeline_metrics",
            "query_custom_metric",
            "query_pipeline_logs",
            "get_pipeline_errors",
            "diagnose_pipeline",
        }
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    def test_registers_resource(self):
        mcp = create_server(MockGlassFlowClient(), MockVMClient(), MockVLClient(), port=0)
        resource_uris = list(mcp._resource_manager._resources.keys())
        assert any("pipeline-v3-format" in str(uri) for uri in resource_uris)
