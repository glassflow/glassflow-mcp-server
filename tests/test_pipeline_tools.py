"""Tests for pipeline CRUD tools."""

from __future__ import annotations

import json

from glassflow_mcp.server import create_server
from tests.conftest import MockGlassFlowClient, MockVLClient, MockVMClient


def _get_tool(mcp, name: str):
    """Look up a registered tool function by name."""
    for tool in mcp._tool_manager._tools.values():
        if tool.name == name:
            return tool.fn
    raise KeyError(f"Tool {name!r} not found")


def _make_server(gf=None, vm=None, vl=None):
    gf = gf or MockGlassFlowClient()
    vm = vm or MockVMClient()
    vl = vl or MockVLClient()
    return create_server(gf, vm, vl, port=0), gf


class TestListPipelines:
    def test_empty(self):
        mcp, _ = _make_server()
        result = _get_tool(mcp, "list_pipelines")()
        assert json.loads(result) == []

    def test_with_pipelines(self):
        mcp, gf = _make_server()
        gf.add_pipeline("pipe-1", name="First", status="Running")
        gf.add_pipeline("pipe-2", name="Second", status="Stopped")
        result = json.loads(_get_tool(mcp, "list_pipelines")())
        assert len(result) == 2
        ids = {p["pipeline_id"] for p in result}
        assert ids == {"pipe-1", "pipe-2"}


class TestGetPipeline:
    def test_found(self):
        mcp, gf = _make_server()
        gf.add_pipeline("my-pipe", name="My Pipeline")
        result = json.loads(_get_tool(mcp, "get_pipeline")("my-pipe"))
        assert result["pipeline_id"] == "my-pipe"
        assert result["name"] == "My Pipeline"

    def test_not_found(self):
        mcp, _ = _make_server()
        result = _get_tool(mcp, "get_pipeline")("nonexistent")
        assert "Error" in result
        assert "not found" in result


class TestGetPipelineHealth:
    def test_running(self):
        mcp, gf = _make_server()
        gf.add_pipeline("healthy-pipe", status="Running")
        result = json.loads(_get_tool(mcp, "get_pipeline_health")("healthy-pipe"))
        assert result["overall_status"] == "Running"


class TestCreatePipeline:
    def test_valid_config(self):
        mcp, _ = _make_server()
        config = json.dumps(
            {
                "version": "v3",
                "pipeline_id": "new-pipe",
                "name": "New Pipeline",
                "sources": [],
                "sink": {},
            }
        )
        result = json.loads(_get_tool(mcp, "create_pipeline")(config))
        assert result["status"] == "created"
        assert result["pipeline_id"] == "new-pipe"

    def test_invalid_json(self):
        mcp, _ = _make_server()
        result = _get_tool(mcp, "create_pipeline")("not json")
        assert "Invalid JSON" in result


class TestStopPipeline:
    def test_success(self):
        mcp, gf = _make_server()
        gf.add_pipeline("running-pipe")
        result = json.loads(_get_tool(mcp, "stop_pipeline")("running-pipe"))
        assert result["status"] == "stopped"

    def test_not_found(self):
        mcp, _ = _make_server()
        result = _get_tool(mcp, "stop_pipeline")("nonexistent")
        assert "Error" in result


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
        patch = json.dumps({"name": "Updated Name"})
        result = json.loads(_get_tool(mcp, "edit_pipeline")("edit-pipe", patch))
        assert result["status"] == "edited"

    def test_invalid_json_patch(self):
        mcp, gf = _make_server()
        gf.add_pipeline("edit-pipe")
        result = _get_tool(mcp, "edit_pipeline")("edit-pipe", "bad json")
        assert "Invalid JSON" in result


class TestDeletePipeline:
    def test_success(self):
        mcp, gf = _make_server()
        gf.add_pipeline("delete-pipe")
        result = json.loads(_get_tool(mcp, "delete_pipeline")("delete-pipe"))
        assert result["status"] == "deleted"
        assert "delete-pipe" not in [p["pipeline_id"] for p in gf.list_pipelines()]
