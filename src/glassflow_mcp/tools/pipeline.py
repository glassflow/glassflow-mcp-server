"""Pipeline CRUD tools for the GlassFlow MCP server."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from glassflow_mcp.glassflow_client import GlassFlowClient


def register_pipeline_tools(mcp: FastMCP, client: GlassFlowClient) -> None:
    """Register all pipeline management tools on the given MCP server."""

    @mcp.tool()
    def list_pipelines() -> str:
        """List all GlassFlow pipelines with their current status.

        Returns a JSON array of pipeline summaries including pipeline_id, name,
        status (Running/Stopped/Created/Failed), and created_at timestamp.

        Use this tool first to discover available pipelines before querying
        specific ones with get_pipeline or get_pipeline_health.
        """
        try:
            pipelines = client.list_pipelines()
            return json.dumps(pipelines, indent=2)
        except Exception as exc:
            return f"Error listing pipelines: {exc}"

    @mcp.tool()
    def get_pipeline(pipeline_id: str) -> str:
        """Get the full configuration of a specific GlassFlow pipeline.

        Returns the complete V3 pipeline configuration as JSON, including
        source, transform, and sink definitions, resource limits, and metadata.

        Use this after list_pipelines to inspect a pipeline's detailed setup.

        Args:
            pipeline_id: The unique identifier of the pipeline (UUID string).
        """
        try:
            pipeline = client.get_pipeline(pipeline_id)
            return json.dumps(pipeline, indent=2)
        except Exception as exc:
            return f"Error getting pipeline {pipeline_id}: {exc}"

    @mcp.tool()
    def get_pipeline_health(pipeline_id: str) -> str:
        """Get the health and runtime status of a GlassFlow pipeline.

        Returns status information including whether the pipeline is running,
        component health, and any error conditions.

        Use this to check if a pipeline is healthy before making changes or
        to diagnose issues with a pipeline that appears to be failing.

        Args:
            pipeline_id: The unique identifier of the pipeline (UUID string).
        """
        try:
            health = client.get_pipeline_health(pipeline_id)
            return json.dumps(health, indent=2)
        except Exception as exc:
            return f"Error getting health for pipeline {pipeline_id}: {exc}"

    @mcp.tool()
    def create_pipeline(config: str) -> str:
        """Create a new GlassFlow pipeline from a V3 pipeline configuration.

        The config parameter must be a JSON string representing a valid V3
        pipeline configuration object. A V3 config typically includes:

        - name: human-readable pipeline name
        - source: source connector definition (e.g. Kafka, HTTP)
        - sink: sink connector definition (e.g. Kafka, ClickHouse)
        - transform: optional transformation definition
        - resources: CPU/memory limits

        Example minimal config:
        {
            "name": "my-pipeline",
            "source": { "connector": "kafka", "config": { ... } },
            "sink": { "connector": "clickhouse", "config": { ... } }
        }

        Returns the full created pipeline configuration including the
        assigned pipeline_id.

        Args:
            config: JSON string of the V3 pipeline configuration.
        """
        try:
            parsed = json.loads(config)
        except json.JSONDecodeError as exc:
            return (
                f"Invalid JSON in config parameter: {exc}. "
                "The config must be a valid JSON string representing "
                "a V3 pipeline configuration."
            )

        try:
            created = client.create_pipeline(parsed)
            return json.dumps(created, indent=2)
        except Exception as exc:
            return f"Error creating pipeline: {exc}"

    @mcp.tool()
    def stop_pipeline(pipeline_id: str) -> str:
        """Stop a running GlassFlow pipeline.

        Sends a stop signal to the pipeline. The pipeline will finish
        processing in-flight messages and then enter the Stopped state.

        Use get_pipeline_health after stopping to confirm the pipeline
        has fully stopped.

        Args:
            pipeline_id: The unique identifier of the pipeline (UUID string).
        """
        try:
            client.stop_pipeline(pipeline_id)
            return f"Pipeline {pipeline_id} stop request sent successfully."
        except Exception as exc:
            return f"Error stopping pipeline {pipeline_id}: {exc}"

    @mcp.tool()
    def resume_pipeline(pipeline_id: str) -> str:
        """Resume a stopped GlassFlow pipeline.

        Restarts a pipeline that was previously stopped. The pipeline will
        resume consuming from where it left off (depending on source
        connector offset semantics).

        Use get_pipeline_health after resuming to confirm the pipeline
        is back in Running state.

        Args:
            pipeline_id: The unique identifier of the pipeline (UUID string).
        """
        try:
            client.resume_pipeline(pipeline_id)
            return f"Pipeline {pipeline_id} resume request sent successfully."
        except Exception as exc:
            return f"Error resuming pipeline {pipeline_id}: {exc}"

    @mcp.tool()
    def delete_pipeline(pipeline_id: str) -> str:
        """Delete a GlassFlow pipeline permanently.

        This action is irreversible. The pipeline and all its associated
        resources will be removed. Stop the pipeline first if it is still
        running.

        Args:
            pipeline_id: The unique identifier of the pipeline (UUID string).
        """
        try:
            client.delete_pipeline(pipeline_id)
            return f"Pipeline {pipeline_id} deleted successfully."
        except Exception as exc:
            return f"Error deleting pipeline {pipeline_id}: {exc}"
