"""Diagnostic tools for the GlassFlow MCP server.

Currently contains the DLQ tool. VictoriaMetrics and VictoriaLogs query
tools will be added here later (ETL-981).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glassflow.etl import Client
    from mcp.server.fastmcp import FastMCP


def register_diagnostics_tools(mcp: FastMCP, client: Client) -> None:
    """Register diagnostic tools on the given MCP server."""

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
            p = client.get_pipeline(pipeline_id)
            state = p.dlq.state()
            return json.dumps(state, indent=2, default=str)
        except Exception as exc:
            return f"Error getting DLQ state for pipeline {pipeline_id}: {exc}"
