"""Tests for diagnostic tools (metrics, logs, DLQ, diagnose)."""

from __future__ import annotations

import json

from glassflow_mcp.server import create_server
from tests.conftest import MockGlassFlowClient, MockVLClient, MockVMClient


def _get_tool(mcp, name: str):
    for tool in mcp._tool_manager._tools.values():
        if tool.name == name:
            return tool.fn
    raise KeyError(f"Tool {name!r} not found")


def _make_server(gf=None, vm=None, vl=None):
    gf = gf or MockGlassFlowClient()
    vm = vm or MockVMClient()
    vl = vl or MockVLClient()
    return create_server(gf, vm, vl, port=0), gf, vm, vl


class TestGetDlqState:
    def test_success(self):
        mcp, gf, _, _ = _make_server()
        gf.add_pipeline("dlq-pipe")
        result = json.loads(_get_tool(mcp, "get_dlq_state")("dlq-pipe"))
        assert result["messages"] == 0

    def test_not_found(self):
        mcp, _, _, _ = _make_server()
        result = _get_tool(mcp, "get_dlq_state")("missing")
        assert "Error" in result


class TestQueryPipelineMetrics:
    def test_with_data(self):
        mcp, gf, vm, _ = _make_server()
        gf.add_pipeline("metric-pipe")
        vm.set_results(
            [
                {"metric": {"pipeline_id": "metric-pipe"}, "value": [1234567, "42.5"]},
            ]
        )
        result = json.loads(
            _get_tool(mcp, "query_pipeline_metrics")("metric-pipe", "throughput_in")
        )
        assert result["metric"] == "throughput_in"
        assert result["results"][0]["value"] == 42.5

    def test_no_data(self):
        mcp, gf, _, _ = _make_server()
        gf.add_pipeline("empty-pipe")
        result = json.loads(_get_tool(mcp, "query_pipeline_metrics")("empty-pipe", "throughput_in"))
        assert result["value"] is None

    def test_unknown_metric(self):
        mcp, _, _, _ = _make_server()
        result = _get_tool(mcp, "query_pipeline_metrics")("pipe", "nonexistent")
        assert "Unknown metric" in result

    def test_invalid_pipeline_id(self):
        mcp, _, _, _ = _make_server()
        result = _get_tool(mcp, "query_pipeline_metrics")('pipe"; drop table', "throughput_in")
        assert "Invalid pipeline_id" in result


class TestQueryCustomMetric:
    def test_allowed_query(self):
        mcp, _, vm, _ = _make_server()
        vm.set_results([{"metric": {}, "value": [0, "1"]}])
        result = json.loads(
            _get_tool(mcp, "query_custom_metric")(
                "my-pipe",
                'glassflow_gfm_processor_messages_total{pipeline_id="my-pipe"}',
            )
        )
        assert len(result["results"]) == 1

    def test_rejected_non_glassflow_metric(self):
        mcp, _, _, _ = _make_server()
        result = _get_tool(mcp, "query_custom_metric")(
            "my-pipe", 'node_cpu_seconds_total{pipeline_id="my-pipe"}'
        )
        assert "Rejected" in result
        assert "glassflow_gfm_" in result

    def test_rejected_missing_pipeline_id(self):
        mcp, _, _, _ = _make_server()
        result = _get_tool(mcp, "query_custom_metric")("my-pipe", "glassflow_gfm_some_metric{}")
        assert "Rejected" in result
        assert "pipeline_id" in result

    def test_invalid_pipeline_id(self):
        mcp, _, _, _ = _make_server()
        result = _get_tool(mcp, "query_custom_metric")('pipe" OR 1=1', "glassflow_gfm_x")
        assert "Invalid pipeline_id" in result


class TestQueryPipelineLogs:
    def test_with_logs(self):
        mcp, gf, _, vl = _make_server()
        gf.add_pipeline("log-pipe")
        vl.set_logs(
            [
                {
                    "_time": "2026-05-11T10:00:00Z",
                    "severity_text": "ERROR",
                    "service.name": "sink",
                    "_msg": "ClickHouse connection refused",
                },
            ]
        )
        result = json.loads(_get_tool(mcp, "query_pipeline_logs")("log-pipe"))
        assert result["count"] == 1
        assert result["logs"][0]["severity"] == "ERROR"

    def test_invalid_component_rejected(self):
        mcp, _, _, _ = _make_server()
        result = _get_tool(mcp, "query_pipeline_logs")("pipe", component='sink" OR _msg:*')
        assert "Invalid component" in result

    def test_invalid_severity_rejected(self):
        mcp, _, _, _ = _make_server()
        result = _get_tool(mcp, "query_pipeline_logs")("pipe", severity='ERROR" OR *')
        assert "Invalid severity" in result


class TestGetPipelineErrors:
    def test_with_errors(self):
        mcp, gf, _, vl = _make_server()
        gf.add_pipeline("err-pipe")
        vl.set_logs(
            [
                {"_time": "t1", "severity_text": "ERROR", "service.name": "sink", "_msg": "fail"},
                {"_time": "t2", "severity_text": "WARN", "service.name": "ingestor", "_msg": "lag"},
            ]
        )
        result = json.loads(_get_tool(mcp, "get_pipeline_errors")("err-pipe"))
        assert result["error_count"] == 2

    def test_no_errors(self):
        mcp, gf, _, _ = _make_server()
        gf.add_pipeline("clean-pipe")
        result = json.loads(_get_tool(mcp, "get_pipeline_errors")("clean-pipe"))
        assert result["error_count"] == 0


class TestDiagnosePipeline:
    def test_full_snapshot(self):
        gf = MockGlassFlowClient()
        vm = MockVMClient()
        vl = MockVLClient()
        gf.add_pipeline("diag-pipe", status="Running")
        vm.set_results([{"metric": {}, "value": [0, "100"]}])
        vl.set_logs(
            [
                {"_time": "t1", "severity_text": "ERROR", "service.name": "sink", "_msg": "oops"},
            ]
        )
        mcp = create_server(gf, vm, vl, port=0)
        result = json.loads(_get_tool(mcp, "diagnose_pipeline")("diag-pipe"))

        assert result["pipeline_id"] == "diag-pipe"
        assert result["status"]["overall_status"] == "Running"
        assert result["metrics"]["throughput_in"] == 100.0
        assert result["dlq"]["messages"] == 0
        assert len(result["recent_errors"]) == 1

    def test_pipeline_not_found(self):
        mcp, _, _, _ = _make_server()
        result = json.loads(_get_tool(mcp, "diagnose_pipeline")("missing"))
        assert "error" in result["status"]

    def test_invalid_pipeline_id(self):
        mcp, _, _, _ = _make_server()
        result = _get_tool(mcp, "diagnose_pipeline")('bad"; id')
        assert "Invalid pipeline_id" in result
