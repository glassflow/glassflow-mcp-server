"""Tests for pipeline CRUD tools."""

from __future__ import annotations

import json

from glassflow_mcp.server import create_server
from tests.conftest import MockGlassFlowClient, make_registry


def _get_tool(mcp, name: str):
    for tool in mcp._tool_manager._tools.values():
        if tool.name == name:
            return tool.fn
    raise KeyError(f"Tool {name!r} not found")


def _make_server(gf=None):
    gf = gf or MockGlassFlowClient()
    reg = make_registry(gf)
    return create_server(reg, port=0), gf


class TestListPipelines:
    def test_empty(self):
        mcp, _ = _make_server()
        assert json.loads(_get_tool(mcp, "list_pipelines")()) == []

    def test_with_pipelines(self):
        mcp, gf = _make_server()
        gf.add_pipeline("pipe-1", name="First", status="Running")
        gf.add_pipeline("pipe-2", name="Second", status="Stopped")
        result = json.loads(_get_tool(mcp, "list_pipelines")())
        assert len(result) == 2


class TestGetPipeline:
    def test_found(self):
        mcp, gf = _make_server()
        gf.add_pipeline("my-pipe", name="My Pipeline")
        result = json.loads(_get_tool(mcp, "get_pipeline")("my-pipe"))
        assert result["pipeline_id"] == "my-pipe"

    def test_not_found(self):
        mcp, _ = _make_server()
        assert "Error" in _get_tool(mcp, "get_pipeline")("nonexistent")


class TestGetPipelineHealth:
    def test_running(self):
        mcp, gf = _make_server()
        gf.add_pipeline("healthy-pipe", status="Running")
        result = json.loads(_get_tool(mcp, "get_pipeline_health")("healthy-pipe"))
        assert result["overall_status"] == "Running"


class TestCreatePipeline:
    def test_valid_config(self):
        mcp, _ = _make_server()
        config = json.dumps({"version": "v3", "pipeline_id": "new-pipe", "sources": [], "sink": {}})
        result = json.loads(_get_tool(mcp, "create_pipeline")(config))
        assert result["status"] == "created"

    def test_invalid_json(self):
        mcp, _ = _make_server()
        assert "Invalid JSON" in _get_tool(mcp, "create_pipeline")("not json")


class TestStopPipeline:
    def test_success(self):
        mcp, gf = _make_server()
        gf.add_pipeline("running-pipe")
        result = json.loads(_get_tool(mcp, "stop_pipeline")("running-pipe"))
        assert result["status"] == "stopped"

    def test_not_found(self):
        mcp, _ = _make_server()
        assert "Error" in _get_tool(mcp, "stop_pipeline")("nonexistent")


class TestResumePipeline:
    def test_success(self):
        mcp, gf = _make_server()
        gf.add_pipeline("stopped-pipe", status="Stopped")
        result = json.loads(_get_tool(mcp, "resume_pipeline")("stopped-pipe"))
        assert result["status"] == "resuming"


class TestEditPipeline:
    def test_valid_patch(self):
        mcp, gf = _make_server()
        gf.add_pipeline("edit-pipe")
        result = json.loads(_get_tool(mcp, "edit_pipeline")("edit-pipe", '{"name": "Updated"}'))
        assert result["status"] == "edited"

    def test_invalid_json_patch(self):
        mcp, gf = _make_server()
        gf.add_pipeline("edit-pipe")
        assert "Invalid JSON" in _get_tool(mcp, "edit_pipeline")("edit-pipe", "bad")


class TestDeletePipeline:
    def test_success(self):
        mcp, gf = _make_server()
        gf.add_pipeline("delete-pipe")
        result = json.loads(_get_tool(mcp, "delete_pipeline")("delete-pipe"))
        assert result["status"] == "deleted"
