"""Tests for the NATS JetStream diagnostic tools and client."""

from __future__ import annotations

import json

import httpx

from glassflow_mcp.nats_client import NATSClient, _format_bytes
from glassflow_mcp.server import create_server
from tests.conftest import MockGlassFlowClient, MockNATSClient, make_registry


def _get_tool(mcp, name: str):
    for tool in mcp._tool_manager._tools.values():
        if tool.name == name:
            return tool.fn
    raise KeyError(f"Tool {name!r} not found")


def _make_server(gf=None, nats=None):
    gf = gf or MockGlassFlowClient()
    nats = nats or MockNATSClient()
    reg = make_registry(gf=gf, nats=nats)
    return create_server(reg, port=0), gf, nats, reg


# A representative stream report as produced by NATSClient.get_stream_report.
_SINK_REPORT = {
    "stream_name": "gfm-abc-sink-in_0",
    "messages": 42,
    "bytes": "4.3 MiB",
    "first_seq": 1,
    "last_seq": 42,
    "subjects": ["gfm-abc-sink-in_0.>"],
    "retention": "limits",
    "consumers": 1,
    "consumer_details": [
        {
            "name": "gf-nats-si-abc",
            "ack_pending": 3,
            "unprocessed": 10,
            "redelivered": 0,
            "waiting_pulls": 0,
            "filter_subject": "gfm-abc-ingestor_left-out.0",
        }
    ],
}


class TestGetPipelineStreams:
    def test_success(self):
        mcp, gf, _, _ = _make_server()
        p = gf.add_pipeline("p1")
        p.set_streams(
            [
                {"stream_name": "gfm-abc-ingestor_left-out_0", "component": "ingestor"},
                {"stream_name": "gfm-abc-sink-in_0", "component": "sink"},
            ]
        )
        result = json.loads(_get_tool(mcp, "get_pipeline_streams")("p1"))
        assert result["count"] == 2
        assert result["streams"][0]["component"] == "ingestor"

    def test_invalid_id(self):
        mcp, _, _, _ = _make_server()
        assert "Invalid pipeline_id" in _get_tool(mcp, "get_pipeline_streams")('bad"; drop')

    def test_pipeline_error(self):
        mcp, _, _, _ = _make_server()
        assert "Error" in _get_tool(mcp, "get_pipeline_streams")("missing")

    def test_get_streams_raises_is_handled(self):
        """A licensing/API error from get_streams surfaces as an error string."""
        mcp, gf, _, _ = _make_server()
        p = gf.add_pipeline("p1")

        def _raise():
            raise Exception("Pipeline streams require a GlassFlow Enterprise license")

        p.get_streams = _raise
        out = _get_tool(mcp, "get_pipeline_streams")("p1")
        assert "Enterprise license" in out


class TestGetStreamReport:
    def test_success(self):
        nats = MockNATSClient()
        nats.set_stream_report("gfm-abc-sink-in_0", _SINK_REPORT)
        mcp, _, _, _ = _make_server(nats=nats)
        result = json.loads(_get_tool(mcp, "get_stream_report")("gfm-abc-sink-in_0"))
        assert result["messages"] == 42
        assert result["consumer_details"][0]["unprocessed"] == 10

    def test_not_found(self):
        mcp, _, _, _ = _make_server()
        result = json.loads(_get_tool(mcp, "get_stream_report")("nope-0"))
        assert "not found" in result["message"].lower()

    def test_invalid_name(self):
        mcp, _, _, _ = _make_server()
        assert "Invalid stream_name" in _get_tool(mcp, "get_stream_report")("bad name!")

    def test_no_nats_client(self):
        mcp, _, _, reg = _make_server()
        reg.active().nats_client = None
        assert "not available" in _get_tool(mcp, "get_stream_report")("gfm-abc-sink-in_0")


class TestGetConsumerReport:
    def test_all_consumers(self):
        nats = MockNATSClient()
        nats.set_stream_report("gfm-abc-sink-in_0", _SINK_REPORT)
        mcp, _, _, _ = _make_server(nats=nats)
        result = json.loads(_get_tool(mcp, "get_consumer_report")("gfm-abc-sink-in_0"))
        assert result["consumer_count"] == 1
        assert result["consumers"][0]["name"] == "gf-nats-si-abc"

    def test_specific_consumer_filter(self):
        nats = MockNATSClient()
        nats.set_stream_report("gfm-abc-sink-in_0", _SINK_REPORT)
        mcp, _, _, _ = _make_server(nats=nats)
        result = json.loads(_get_tool(mcp, "get_consumer_report")("gfm-abc-sink-in_0", "no-such"))
        assert result["consumer_count"] == 0

    def test_stream_missing(self):
        mcp, _, _, _ = _make_server()
        result = json.loads(_get_tool(mcp, "get_consumer_report")("nope-0"))
        assert "not found" in result["message"].lower()


class TestDiagnosePipelineNats:
    def test_nats_streams_section_present(self):
        nats = MockNATSClient()
        nats.set_stream_report("gfm-abc-sink-in_0", _SINK_REPORT)
        mcp, gf, _, _ = _make_server(nats=nats)
        p = gf.add_pipeline("p1")
        p.set_streams([{"stream_name": "gfm-abc-sink-in_0", "component": "sink"}])
        result = json.loads(_get_tool(mcp, "diagnose_pipeline")("p1"))
        assert "nats_streams" in result
        section = result["nats_streams"]["gfm-abc-sink-in_0"]
        assert section["component"] == "sink"
        assert section["messages"] == 42

    def test_no_nats_client_message(self):
        mcp, gf, _, reg = _make_server()
        reg.active().nats_client = None
        gf.add_pipeline("p1")  # no streams set -> []
        result = json.loads(_get_tool(mcp, "diagnose_pipeline")("p1"))
        assert "nats_streams" in result


# ---------------------------------------------------------------------------
# NATSClient unit tests (parsing the /jsz monitoring payload)
# ---------------------------------------------------------------------------

_JSZ = {
    "account_details": [
        {
            "name": "$G",
            "stream_detail": [
                {
                    "name": "gfm-abc-sink-in_0",
                    "state": {
                        "messages": 42,
                        "bytes": 4509715,
                        "first_seq": 1,
                        "last_seq": 42,
                        "consumer_count": 1,
                    },
                    "config": {
                        "subjects": ["gfm-abc-sink-in_0.>"],
                        "retention": "limits",
                    },
                    "consumer_detail": [
                        {
                            "name": "gf-nats-si-abc",
                            "num_ack_pending": 3,
                            "num_pending": 10,
                            "num_redelivered": 1,
                            "num_waiting": 0,
                            "config": {"filter_subject": "gfm-abc-ingestor_left-out.0"},
                        }
                    ],
                }
            ],
        }
    ]
}


def _client_returning(payload: dict) -> NATSClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/jsz"
        return httpx.Response(200, json=payload)

    client = NATSClient(base_url="http://nats:8222")
    client._client = httpx.Client(
        base_url="http://nats:8222", transport=httpx.MockTransport(handler)
    )
    return client


class TestNATSClientParsing:
    def test_stream_report(self):
        c = _client_returning(_JSZ)
        report = c.get_stream_report("gfm-abc-sink-in_0")
        assert report is not None
        assert report["messages"] == 42
        assert report["bytes"] == "4.3 MiB"
        assert report["last_seq"] == 42
        assert report["subjects"] == ["gfm-abc-sink-in_0.>"]
        assert report["consumers"] == 1
        cons = report["consumer_details"][0]
        assert cons["ack_pending"] == 3
        assert cons["unprocessed"] == 10
        assert cons["filter_subject"] == "gfm-abc-ingestor_left-out.0"

    def test_stream_not_found(self):
        c = _client_returning(_JSZ)
        assert c.get_stream_report("does-not-exist") is None

    def test_consumer_report_all_and_filtered(self):
        c = _client_returning(_JSZ)
        all_c = c.get_consumer_report("gfm-abc-sink-in_0")
        assert all_c["consumer_count"] == 1
        filtered = c.get_consumer_report("gfm-abc-sink-in_0", "gf-nats-si-abc")
        assert filtered["consumer_count"] == 1
        missing = c.get_consumer_report("gfm-abc-sink-in_0", "ghost")
        assert missing["consumer_count"] == 0

    def test_format_bytes(self):
        assert _format_bytes(0) == "0 B"
        assert _format_bytes(1536) == "1.5 KiB"
        assert _format_bytes(4509715) == "4.3 MiB"


class TestNATSClientClusterAware:
    """A node's /jsz only lists locally-hosted streams; the client must query
    every cluster node and merge (the 'stream not found' bug)."""

    @staticmethod
    def _stream_payload(name: str) -> dict:
        return {
            "account_details": [
                {
                    "name": "$G",
                    "stream_detail": [
                        {"name": name, "state": {}, "config": {}, "consumer_detail": []}
                    ],
                }
            ]
        }

    def _two_node_client(self) -> NATSClient:
        # node 10.0.0.1 hosts only stream-a; node 10.0.0.2 hosts only stream-b.
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/jsz"
            name = "stream-a" if request.url.host == "10.0.0.1" else "stream-b"
            return httpx.Response(200, json=self._stream_payload(name))

        client = NATSClient(base_url="http://nats-headless:8222")
        client._client = httpx.Client(transport=httpx.MockTransport(handler))
        client._endpoints = lambda: ["http://10.0.0.1:8222", "http://10.0.0.2:8222"]
        return client

    def test_finds_stream_on_any_node(self):
        c = self._two_node_client()
        # stream-b lives on the second node — a single-node query would miss it.
        assert c.get_stream_report("stream-a") is not None
        assert c.get_stream_report("stream-b") is not None
        assert c.get_stream_report("stream-c") is None

    def test_endpoints_fall_back_when_dns_fails(self):
        # .invalid never resolves (RFC 2606) -> use the configured URL as-is.
        c = NATSClient(base_url="http://no-such-host.invalid:8222")
        assert c._endpoints() == ["http://no-such-host.invalid:8222"]

    def test_one_node_down_does_not_blank_others(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "10.0.0.1":
                raise httpx.ConnectError("node down")
            return httpx.Response(200, json=self._stream_payload("stream-b"))

        c = NATSClient(base_url="http://nats-headless:8222")
        c._client = httpx.Client(transport=httpx.MockTransport(handler))
        c._endpoints = lambda: ["http://10.0.0.1:8222", "http://10.0.0.2:8222"]
        assert c.get_stream_report("stream-b") is not None
