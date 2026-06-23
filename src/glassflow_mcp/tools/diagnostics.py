"""Diagnostic tools for the GlassFlow MCP server.

Tools for querying pipeline metrics (VictoriaMetrics), logs
(VictoriaLogs), DLQ state, and a composite diagnose_pipeline tool
that gives an AI agent a complete pipeline health snapshot.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from glassflow_mcp.cluster import ClusterRegistry

logger = logging.getLogger(__name__)

# Allowed characters for identifiers injected into PromQL/LogsQL queries.
# Prevents injection by rejecting anything outside this safe set.
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")

# Only metric names matching this prefix are allowed in custom queries.
#
# The GlassFlow engine emits all signals under the bare `gfm_*` prefix. The
# `prometheusremotewrite` exporter that feeds VictoriaMetrics (which this server
# queries) does NOT prepend the service name, so VM stores `gfm_kafka_records_read_total`
# etc. There is NO `glassflow_gfm_*` series — that prefix only exists on the pull-only
# Prometheus `/metrics` endpoint (namespaced `glassflow_ee_gfm_*`), which we never read.
# Using `glassflow_gfm_*` here matches zero series and every metric returns null.
_ALLOWED_METRIC_PREFIX = "gfm_"

# Pre-built PromQL templates keyed by metric name.
# {pid} is replaced with the actual pipeline_id at query time.
_METRIC_QUERIES = {
    # Kafka ingestor reads OR OTLP receiver hand-offs — a pipeline is always one
    # type, never both, so `or` returns whichever side has series. The OTLP
    # components are `otlp.logs`/`otlp.metrics`/`otlp.traces`; we match them with
    # `otlp.*` rather than escaping the dot — a backslash inside a PromQL
    # double-quoted string is an invalid escape and VM rejects it with HTTP 422.
    "throughput_in": (
        'sum(rate(gfm_kafka_records_read_total{{pipeline_id="{pid}",component="ingestor"}}[5m]))'
        " or "
        'sum(rate(gfm_processor_messages_total{{pipeline_id="{pid}",'
        'component=~"otlp.*",status="out"}}[5m]))'
    ),
    "throughput_out": (
        'sum(rate(gfm_clickhouse_records_written_total{{pipeline_id="{pid}"}}[5m]))'
    ),
    # No gauge for write rate is emitted; use a short-window rate of the sink counter.
    "write_rate": ('sum(rate(gfm_clickhouse_records_written_total{{pipeline_id="{pid}"}}[1m]))'),
    # histogram_quantile needs the buckets summed by `le` across the per-component
    # /per-instance series, otherwise it computes per-series quantiles (or nothing).
    "latency_p95": (
        "histogram_quantile(0.95, "
        'sum by (le) (rate(gfm_processing_duration_seconds_bucket{{pipeline_id="{pid}"}}[5m])))'
    ),
    "dlq_rate": ('sum(rate(gfm_dlq_records_written_total{{pipeline_id="{pid}"}}[5m]))'),
    "bytes_in": ('sum(rate(gfm_bytes_processed_total{{pipeline_id="{pid}",direction="in"}}[5m]))'),
    "bytes_out": (
        'sum(rate(gfm_bytes_processed_total{{pipeline_id="{pid}",direction="out"}}[5m]))'
    ),
}


def _validate_id(value: str, name: str) -> str | None:
    """Return an error message if *value* contains unsafe characters, else None."""
    if not value or not _SAFE_ID_RE.match(value):
        return f"Invalid {name}: must match [a-zA-Z0-9_.\\-]+, got {value!r}"
    return None


def _format_log_entry(log: dict) -> dict:
    """Extract standard fields from a VictoriaLogs result entry."""
    return {
        "timestamp": log.get("_time", ""),
        "severity": log.get("severity_text", log.get("SeverityText", "")),
        "service": log.get("service.name", ""),
        "message": log.get("_msg", log.get("body", "")),
    }


def _collect_nats_streams(conn, streams: list[dict]) -> dict:
    """Build the diagnose_pipeline ``nats_streams`` section.

    For each stream returned by ``pipeline.get_streams()`` (each a
    ``{stream_name, component, ...}`` dict), look up its live NATS report
    and merge it in, keyed by stream name. Failures are captured per
    stream so one bad stream never breaks the whole snapshot.
    """
    nats = conn.nats_client if conn else None
    if nats is None:
        return {"message": "No NATS monitoring URL configured for this cluster"}

    out: dict = {}
    for s in streams:
        name = s.get("stream_name")
        if not name:
            continue
        entry: dict = {"component": s.get("component", "")}
        if s.get("source_id"):
            entry["source_id"] = s["source_id"]
        try:
            report = nats.get_stream_report(name)
        except Exception as exc:
            entry["error"] = str(exc)
            out[name] = entry
            continue
        if report is None:
            entry["message"] = "stream not found in NATS (pipeline may be stopped)"
        else:
            report.pop("stream_name", None)
            entry.update(report)
        out[name] = entry
    return out


def register_diagnostics_tools(
    mcp: FastMCP,
    registry: ClusterRegistry,
) -> None:
    """Register diagnostic tools on the given MCP server."""

    # -----------------------------------------------------------------
    # DLQ
    # -----------------------------------------------------------------

    @mcp.tool()
    def get_dlq_state(pipeline_id: str) -> str:
        """Get the dead-letter queue (DLQ) state for a GlassFlow pipeline.

        Returns the current DLQ state including the number of messages that
        failed processing and were routed to the DLQ. A non-zero count
        typically indicates schema validation errors, type mismatches, or
        sink connection issues.

        Use this when diagnosing pipeline issues, especially if the pipeline
        is running but data is not reaching ClickHouse.

        Args:
            pipeline_id: The unique identifier of the pipeline.
        """
        try:
            conn = registry.active()
            p = conn.gf_client.get_pipeline(pipeline_id)
            state = p.dlq.state()
            return json.dumps(state, indent=2, default=str)
        except Exception as exc:
            logger.exception("get_dlq_state failed for %s", pipeline_id)
            return f"Error getting DLQ state for pipeline {pipeline_id}: {exc}"

    # -----------------------------------------------------------------
    # Metrics (VictoriaMetrics)
    # -----------------------------------------------------------------

    @mcp.tool()
    def query_pipeline_metrics(
        pipeline_id: str,
        metric: str = "throughput_in",
    ) -> str:
        """Query a specific metric for a GlassFlow pipeline.

        Available metrics:
          - throughput_in:  records/sec consumed from Kafka
          - throughput_out: records/sec written to ClickHouse
          - write_rate:     current ClickHouse write rate (gauge)
          - latency_p95:    95th percentile processing duration
          - dlq_rate:       records/sec sent to the dead-letter queue
          - bytes_in:       bytes/sec ingested
          - bytes_out:      bytes/sec written

        Returns the current instant value of the metric. Use this to
        check specific throughput or latency numbers after running
        diagnose_pipeline for the overview.

        Args:
            pipeline_id: The unique identifier of the pipeline.
            metric: Metric name from the list above (default: throughput_in).
        """
        if err := _validate_id(pipeline_id, "pipeline_id"):
            return err

        template = _METRIC_QUERIES.get(metric)
        if not template:
            available = ", ".join(sorted(_METRIC_QUERIES))
            return f"Unknown metric '{metric}'. Available: {available}"

        query = template.format(pid=pipeline_id)
        try:
            vm = registry.active().vm_client
            if vm is None:
                return "Metrics not available — no VictoriaMetrics URL configured for this cluster."
            results = vm.instant_query(query)
            if not results:
                return json.dumps(
                    {
                        "metric": metric,
                        "pipeline_id": pipeline_id,
                        "value": None,
                        "message": "No data — the pipeline may not be running or "
                        "metrics have not been scraped yet.",
                    },
                    indent=2,
                )
            formatted = []
            for r in results:
                entry = {**r["metric"], "value": float(r["value"][1])}
                formatted.append(entry)
            return json.dumps(
                {"metric": metric, "pipeline_id": pipeline_id, "results": formatted},
                indent=2,
                default=str,
            )
        except Exception as exc:
            logger.exception("query_pipeline_metrics failed for %s", pipeline_id)
            return f"Error querying metric '{metric}' for {pipeline_id}: {exc}"

    @mcp.tool()
    def query_custom_metric(pipeline_id: str, promql: str) -> str:
        """Run a custom PromQL query for GlassFlow metrics.

        Only queries against gfm_* metrics are allowed (the prefix
        VictoriaMetrics actually stores). The query must include a
        pipeline_id filter matching the provided pipeline_id.

        Example:
          rate(gfm_processor_messages_total{pipeline_id="my-pipe",status="filtered"}[5m])

        Args:
            pipeline_id: Pipeline ID — must appear in the query.
            promql: PromQL query (must reference gfm_* metrics).
        """
        if err := _validate_id(pipeline_id, "pipeline_id"):
            return err

        # Security: only allow glassflow metrics
        if _ALLOWED_METRIC_PREFIX not in promql:
            return (
                f"Rejected: query must reference {_ALLOWED_METRIC_PREFIX}* metrics. "
                f"Use query_pipeline_metrics for pre-built queries."
            )

        # Security: require pipeline_id in the query
        if pipeline_id not in promql:
            return f'Rejected: query must include pipeline_id="{pipeline_id}" filter.'

        try:
            vm = registry.active().vm_client
            if vm is None:
                return "Metrics not available — no VictoriaMetrics URL configured for this cluster."
            results = vm.instant_query(promql)
            return json.dumps(
                {"query": promql, "pipeline_id": pipeline_id, "results": results},
                indent=2,
                default=str,
            )
        except Exception as exc:
            logger.exception("query_custom_metric failed")
            return f"Error running custom query: {exc}"

    # -----------------------------------------------------------------
    # Logs (VictoriaLogs)
    # -----------------------------------------------------------------

    @mcp.tool()
    def query_pipeline_logs(
        pipeline_id: str,
        severity: str = "",
        component: str = "",
        limit: int = 30,
    ) -> str:
        """Query recent logs for a GlassFlow pipeline.

        Returns log lines from pipeline components (ingestor, dedup, sink,
        join, etc.) filtered by pipeline_id, severity, and component.

        Args:
            pipeline_id: The unique identifier of the pipeline.
            severity: Filter by log severity (error, warn, info, debug).
                      Leave empty for all severities.
            component: Filter by component (ingestor, dedup, sink, join).
                       Leave empty for all components.
            limit: Maximum number of log lines to return (default: 30).
        """
        if err := _validate_id(pipeline_id, "pipeline_id"):
            return err
        if severity and (err := _validate_id(severity, "severity")):
            return err
        if component and (err := _validate_id(component, "component")):
            return err

        parts = [f'pipeline_id:"{pipeline_id}"']
        if severity:
            parts.append(f'severity_text:"{severity.upper()}"')
        if component:
            parts.append(f'service.name:"{component}"')
        query = " AND ".join(parts)

        try:
            vl = registry.active().vl_client
            if vl is None:
                return "Logs not available — no VictoriaLogs URL configured for this cluster."
            logs = vl.query(query, limit=limit)
            formatted = [_format_log_entry(log) for log in logs]
            return json.dumps(
                {
                    "pipeline_id": pipeline_id,
                    "count": len(formatted),
                    "logs": formatted,
                },
                indent=2,
                default=str,
            )
        except Exception as exc:
            logger.exception("query_pipeline_logs failed for %s", pipeline_id)
            return f"Error querying logs for {pipeline_id}: {exc}"

    @mcp.tool()
    def get_pipeline_errors(pipeline_id: str, limit: int = 15) -> str:
        """Get recent ERROR and WARN logs for a pipeline.

        This is the "what's wrong?" shortcut — returns only error and
        warning level logs, newest first. Use this as the first step
        when investigating a failing or degraded pipeline.

        Args:
            pipeline_id: The unique identifier of the pipeline.
            limit: Maximum number of error/warn lines (default: 15).
        """
        if err := _validate_id(pipeline_id, "pipeline_id"):
            return err

        query = f'pipeline_id:"{pipeline_id}" AND (severity_text:"ERROR" OR severity_text:"WARN")'
        try:
            vl = registry.active().vl_client
            if vl is None:
                return "Logs not available — no VictoriaLogs URL configured for this cluster."
            logs = vl.query(query, limit=limit)
            formatted = [_format_log_entry(log) for log in logs]
            return json.dumps(
                {
                    "pipeline_id": pipeline_id,
                    "error_count": len(formatted),
                    "errors": formatted,
                },
                indent=2,
                default=str,
            )
        except Exception as exc:
            logger.exception("get_pipeline_errors failed for %s", pipeline_id)
            return f"Error getting errors for {pipeline_id}: {exc}"

    # -----------------------------------------------------------------
    # NATS JetStream (Enterprise)
    # -----------------------------------------------------------------

    @mcp.tool()
    def get_pipeline_streams(pipeline_id: str) -> str:
        """List the NATS JetStream streams backing a GlassFlow pipeline.

        Returns each stream's name and the component it belongs to
        (ingestor, dedup, join, sink, dlq), plus the source_id where
        applicable. Use this FIRST to discover stream names, then pass a
        stream_name to get_stream_report or get_consumer_report for live
        message counts and consumer health.

        Note: this is an Enterprise feature. On a non-licensed backend it
        returns a licensing error.

        Args:
            pipeline_id: The unique identifier of the pipeline.
        """
        if err := _validate_id(pipeline_id, "pipeline_id"):
            return err
        try:
            conn = registry.active()
            p = conn.gf_client.get_pipeline(pipeline_id)
            streams = p.get_streams()
            return json.dumps(
                {"pipeline_id": pipeline_id, "count": len(streams), "streams": streams},
                indent=2,
                default=str,
            )
        except Exception as exc:
            logger.exception("get_pipeline_streams failed for %s", pipeline_id)
            return f"Error getting streams for pipeline {pipeline_id}: {exc}"

    @mcp.tool()
    def get_stream_report(stream_name: str) -> str:
        """Get a detailed NATS JetStream stream report.

        Returns message count, byte size, sequence numbers, subject list,
        retention policy, and a per-consumer breakdown (ack-pending,
        unprocessed backlog, filter subject) for the specified stream.

        Use get_pipeline_streams first to discover stream names for a
        pipeline, then use this tool to inspect specific streams. A stream
        with messages but zero consumers, or a consumer with a growing
        unprocessed count, points to stalled data flow.

        Args:
            stream_name: The NATS stream name (e.g., gfm-abc123-ingestor_left-out_0).
        """
        if err := _validate_id(stream_name, "stream_name"):
            return err
        try:
            nats = registry.active().nats_client
            if nats is None:
                return (
                    "NATS monitoring not available — no NATS monitoring URL "
                    "configured for this cluster."
                )
            report = nats.get_stream_report(stream_name)
            if report is None:
                return json.dumps(
                    {
                        "stream_name": stream_name,
                        "message": "Stream not found in NATS. The pipeline may be "
                        "stopped, or the stream name may be wrong — use "
                        "get_pipeline_streams to list valid names.",
                    },
                    indent=2,
                )
            return json.dumps(report, indent=2, default=str)
        except Exception as exc:
            logger.exception("get_stream_report failed for %s", stream_name)
            return f"Error getting stream report for {stream_name}: {exc}"

    @mcp.tool()
    def get_consumer_report(stream_name: str, consumer_name: str = "") -> str:
        """Get a NATS JetStream consumer report for a stream.

        Returns each consumer's ack-pending count, unprocessed (undelivered)
        backlog, redelivery count, and filter subject. If consumer_name is
        omitted, reports all consumers on the stream.

        Diagnostic signals:
          - ack_pending > 0 and not draining: a stuck/slow consumer
          - unprocessed growing: the consumer is falling behind (backlog)
          - filter_subject not matching the stream's subjects: the
            subject-mismatch bug pattern (zero output)

        Args:
            stream_name: The NATS stream name.
            consumer_name: Optional specific consumer; omit for all consumers.
        """
        if err := _validate_id(stream_name, "stream_name"):
            return err
        if consumer_name and (err := _validate_id(consumer_name, "consumer_name")):
            return err
        try:
            nats = registry.active().nats_client
            if nats is None:
                return (
                    "NATS monitoring not available — no NATS monitoring URL "
                    "configured for this cluster."
                )
            report = nats.get_consumer_report(stream_name, consumer_name or None)
            if report is None:
                return json.dumps(
                    {
                        "stream_name": stream_name,
                        "message": "Stream not found in NATS. Use "
                        "get_pipeline_streams to list valid stream names.",
                    },
                    indent=2,
                )
            return json.dumps(report, indent=2, default=str)
        except Exception as exc:
            logger.exception("get_consumer_report failed for %s", stream_name)
            return f"Error getting consumer report for {stream_name}: {exc}"

    # -----------------------------------------------------------------
    # Composite diagnostic
    # -----------------------------------------------------------------

    @mcp.tool()
    def diagnose_pipeline(pipeline_id: str) -> str:
        """Get a complete diagnostic snapshot of a GlassFlow pipeline.

        This is the most important diagnostic tool. It combines pipeline
        health, throughput metrics, DLQ state, and recent error logs into
        a single response. Use this FIRST when a user reports a pipeline
        issue — it gives you everything needed to identify the problem.

        Returns:
          - status: pipeline health and overall status
          - metrics: throughput_in, throughput_out, write_rate, latency_p95
          - dlq: dead-letter queue message count
          - recent_errors: last 10 ERROR/WARN log lines
          - nats_streams: per-stream message counts and consumer health
            (Enterprise; absent if NATS monitoring is not configured)

        Args:
            pipeline_id: The unique identifier of the pipeline.
        """
        if err := _validate_id(pipeline_id, "pipeline_id"):
            return err

        result: dict = {"pipeline_id": pipeline_id}

        # 1. Health / status + reuse pipeline object for DLQ
        p = None
        try:
            conn = registry.active()
            p = conn.gf_client.get_pipeline(pipeline_id)
            result["status"] = p.health()
        except Exception as exc:
            logger.exception("diagnose_pipeline: health failed for %s", pipeline_id)
            result["status"] = {"error": str(exc)}

        # 2. Throughput metrics
        metrics: dict = {}
        try:
            conn = registry.active()
        except RuntimeError:
            conn = None
        vm = conn.vm_client if conn else None
        if vm:
            for metric_key in (
                "throughput_in",
                "throughput_out",
                "write_rate",
                "latency_p95",
            ):
                template = _METRIC_QUERIES[metric_key]
                query = template.format(pid=pipeline_id)
                try:
                    metrics[metric_key] = vm.get_metric_value(query)
                except Exception:
                    metrics[metric_key] = None
        result["metrics"] = metrics or {"message": "No VictoriaMetrics configured"}

        # 3. DLQ state (reuse pipeline object from step 1)
        if p:
            try:
                result["dlq"] = p.dlq.state()
            except Exception as exc:
                result["dlq"] = {"error": str(exc)}
        else:
            result["dlq"] = {"error": "Pipeline not reachable"}

        # 4. Recent errors
        vl = conn.vl_client if conn else None
        if vl:
            error_query = (
                f'pipeline_id:"{pipeline_id}" AND (severity_text:"ERROR" OR severity_text:"WARN")'
            )
            try:
                logs = vl.query(error_query, limit=10)
                result["recent_errors"] = [_format_log_entry(log) for log in logs]
            except Exception as exc:
                logger.exception("diagnose_pipeline: logs failed for %s", pipeline_id)
                result["recent_errors"] = {"error": str(exc)}
        else:
            result["recent_errors"] = {"message": "No VictoriaLogs configured"}

        # 5. NATS JetStream health (Enterprise). Reuse pipeline object from step 1.
        if p and conn:
            try:
                streams = p.get_streams()
                result["nats_streams"] = _collect_nats_streams(conn, streams)
            except Exception as exc:
                logger.exception("diagnose_pipeline: nats streams failed for %s", pipeline_id)
                result["nats_streams"] = {"error": str(exc)}
        else:
            result["nats_streams"] = {"error": "Pipeline not reachable"}

        return json.dumps(result, indent=2, default=str)
