"""NATS JetStream monitoring client.

Queries the NATS HTTP monitoring API (``/jsz``) to report on JetStream
stream and consumer health. This is the synchronous, dependency-free
alternative to the async ``nats-py`` client — it matches the VM/VL
client pattern and avoids pulling an event loop into the sync MCP tools.

See https://docs.nats.io/running-a-nats-service/nats_admin/monitoring
"""

from __future__ import annotations

import logging
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Query params that ask /jsz for per-stream and per-consumer detail,
# including the config blocks (needed for subjects + filter_subject).
_JSZ_PARAMS = {"streams": "true", "consumers": "true", "config": "true"}


def _format_bytes(num: int | float) -> str:
    """Human-readable byte size (e.g. 4.3 MiB)."""
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TiB"


def _format_consumer(consumer: dict[str, Any]) -> dict[str, Any]:
    """Extract the diagnostic-relevant fields from a /jsz consumer_detail entry."""
    config = consumer.get("config", {})
    return {
        "name": consumer.get("name", ""),
        # Messages delivered but not yet acked — a stuck consumer shows this > 0.
        "ack_pending": consumer.get("num_ack_pending", 0),
        # Messages in the stream not yet delivered to this consumer (backlog).
        "unprocessed": consumer.get("num_pending", 0),
        "redelivered": consumer.get("num_redelivered", 0),
        "waiting_pulls": consumer.get("num_waiting", 0),
        # The subject the consumer binds to — a mismatch vs the stream's
        # subjects is the zero-output bug pattern.
        "filter_subject": config.get("filter_subject", ""),
    }


class NATSClient:
    """Query NATS JetStream health via the HTTP monitoring API.

    Cluster-aware: a node's ``/jsz`` only reports streams whose assets are
    hosted on *that* node. With ``Replicas: 1`` streams are scattered across
    the cluster, so querying a single node makes streams led by other nodes
    look like they don't exist (a "stream not found" false negative). We
    therefore resolve the configured host to every backing IP
    (point this at the NATS *headless* service so DNS returns all pods) and
    merge ``/jsz`` across all of them.
    """

    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        # No base_url on the client — we issue absolute URLs, one per node.
        self._client = httpx.Client(timeout=timeout)

    def _endpoints(self) -> list[str]:
        """Resolve the configured host to one monitoring URL per cluster node.

        Falls back to the configured URL as-is if DNS resolution yields
        nothing (e.g. unit tests with a mock transport).
        """
        parsed = urlparse(self._base_url)
        host, port = parsed.hostname, parsed.port
        scheme = parsed.scheme or "http"
        try:
            ips = sorted(
                {info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
            )
        except OSError:
            logger.warning("NATS host %r did not resolve; using configured URL as-is", host)
            ips = []
        if not ips:
            return [self._base_url]
        port_part = f":{port}" if port else ""
        # Bracket IPv6 literals for a valid URL authority.
        return [f"{scheme}://{f'[{ip}]' if ':' in ip else ip}{port_part}" for ip in ips]

    def _iter_jsz(self):
        """Yield the /jsz JetStream report from each cluster node, skipping
        nodes that error so one unreachable pod never blanks the whole view."""
        for endpoint in self._endpoints():
            try:
                resp = self._client.get(f"{endpoint}/jsz", params=_JSZ_PARAMS)
                resp.raise_for_status()
                yield resp.json()
            except httpx.HTTPError as exc:
                logger.warning("NATS /jsz query failed for %s: %s", endpoint, exc)
                continue

    def _find_stream(self, stream_name: str) -> dict[str, Any] | None:
        """Locate a stream's detail block across all nodes/accounts, or None."""
        for report in self._iter_jsz():
            for account in report.get("account_details", []):
                for stream in account.get("stream_detail", []):
                    if stream.get("name") == stream_name:
                        return stream
        return None

    def get_stream_report(self, stream_name: str) -> dict[str, Any] | None:
        """Return a stream report, or None if the stream does not exist.

        Includes message/byte counts, sequence range, subjects, retention
        policy, and a per-consumer breakdown.
        """
        stream = self._find_stream(stream_name)
        if stream is None:
            return None

        state = stream.get("state", {})
        config = stream.get("config", {})
        consumers = stream.get("consumer_detail", [])
        return {
            "stream_name": stream_name,
            "messages": state.get("messages", 0),
            "bytes": _format_bytes(state.get("bytes", 0)),
            "first_seq": state.get("first_seq", 0),
            "last_seq": state.get("last_seq", 0),
            "subjects": config.get("subjects", []),
            "retention": config.get("retention", ""),
            "consumers": state.get("consumer_count", len(consumers)),
            "consumer_details": [_format_consumer(c) for c in consumers],
        }

    def get_consumer_report(
        self,
        stream_name: str,
        consumer_name: str | None = None,
    ) -> dict[str, Any] | None:
        """Return consumer report(s) for a stream, or None if stream is missing.

        With ``consumer_name`` omitted, returns all consumers on the stream.
        Returns an empty list (not None) when the stream exists but has no
        matching consumer.
        """
        stream = self._find_stream(stream_name)
        if stream is None:
            return None

        consumers = [_format_consumer(c) for c in stream.get("consumer_detail", [])]
        if consumer_name:
            consumers = [c for c in consumers if c["name"] == consumer_name]
        return {
            "stream_name": stream_name,
            "consumer_count": len(consumers),
            "consumers": consumers,
        }

    def healthy(self) -> bool:
        """True if any cluster node answers /healthz."""
        for endpoint in self._endpoints():
            try:
                resp = self._client.get(f"{endpoint}/healthz")
                if resp.is_success:
                    return True
            except httpx.HTTPError:
                continue
        return False

    def close(self) -> None:
        self._client.close()
