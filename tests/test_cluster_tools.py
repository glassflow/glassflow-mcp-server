"""Tests for cluster management tools."""

from __future__ import annotations

import json

from glassflow_mcp.cluster import ClusterRegistry
from glassflow_mcp.server import create_server


def _get_tool(mcp, name: str):
    for tool in mcp._tool_manager._tools.values():
        if tool.name == name:
            return tool.fn
    raise KeyError(f"Tool {name!r} not found")


class TestConnectCluster:
    def test_first_cluster_becomes_active(self):
        reg = ClusterRegistry()
        mcp = create_server(reg, port=0)
        result = json.loads(_get_tool(mcp, "connect_cluster")("staging", "http://staging-api:8081"))
        assert result["status"] == "connected"
        assert result["cluster"] == "staging"
        assert result["active"] is True

    def test_second_cluster_not_active(self):
        reg = ClusterRegistry()
        mcp = create_server(reg, port=0)
        _get_tool(mcp, "connect_cluster")("first", "http://first:8081")
        result = json.loads(_get_tool(mcp, "connect_cluster")("second", "http://second:8081"))
        assert result["active"] is False

    def test_with_vm_and_vl(self):
        reg = ClusterRegistry()
        mcp = create_server(reg, port=0)
        result = json.loads(
            _get_tool(mcp, "connect_cluster")(
                "full",
                "http://api:8081",
                vm_url="http://vm:8428",
                vl_url="http://vl:9428",
            )
        )
        assert result["status"] == "connected"
        clusters = json.loads(_get_tool(mcp, "list_clusters")())
        assert clusters["clusters"][0]["vm_url"] == "http://vm:8428"


class TestListClusters:
    def test_empty(self):
        reg = ClusterRegistry()
        mcp = create_server(reg, port=0)
        result = json.loads(_get_tool(mcp, "list_clusters")())
        assert result["clusters"] == []
        assert "No clusters" in result["message"]

    def test_multiple_clusters(self):
        reg = ClusterRegistry()
        mcp = create_server(reg, port=0)
        _get_tool(mcp, "connect_cluster")("staging", "http://staging:8081")
        _get_tool(mcp, "connect_cluster")("prod", "http://prod:8081")
        result = json.loads(_get_tool(mcp, "list_clusters")())
        names = {c["name"] for c in result["clusters"]}
        assert names == {"staging", "prod"}
        active = [c for c in result["clusters"] if c["active"]]
        assert len(active) == 1
        assert active[0]["name"] == "staging"


class TestSwitchCluster:
    def test_switch(self):
        reg = ClusterRegistry()
        mcp = create_server(reg, port=0)
        _get_tool(mcp, "connect_cluster")("a", "http://a:8081")
        _get_tool(mcp, "connect_cluster")("b", "http://b:8081")
        result = json.loads(_get_tool(mcp, "switch_cluster")("b"))
        assert result["active_cluster"] == "b"

    def test_switch_nonexistent(self):
        reg = ClusterRegistry()
        mcp = create_server(reg, port=0)
        result = _get_tool(mcp, "switch_cluster")("missing")
        assert "not found" in result


class TestDisconnectCluster:
    def test_disconnect(self):
        reg = ClusterRegistry()
        mcp = create_server(reg, port=0)
        _get_tool(mcp, "connect_cluster")("temp", "http://temp:8081")
        result = json.loads(_get_tool(mcp, "disconnect_cluster")("temp"))
        assert result["status"] == "disconnected"
        clusters = json.loads(_get_tool(mcp, "list_clusters")())
        assert clusters["clusters"] == []

    def test_disconnect_active_switches(self):
        reg = ClusterRegistry()
        mcp = create_server(reg, port=0)
        _get_tool(mcp, "connect_cluster")("a", "http://a:8081")
        _get_tool(mcp, "connect_cluster")("b", "http://b:8081")
        result = json.loads(_get_tool(mcp, "disconnect_cluster")("a"))
        assert result["active_cluster"] == "b"


class TestNoClusterConnected:
    def test_pipeline_tool_fails_gracefully(self):
        reg = ClusterRegistry()
        mcp = create_server(reg, port=0)
        result = _get_tool(mcp, "list_pipelines")()
        assert "No cluster connected" in result
