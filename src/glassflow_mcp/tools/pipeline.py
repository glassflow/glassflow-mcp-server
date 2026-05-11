"""Pipeline CRUD tools for the GlassFlow MCP server."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glassflow.etl import Client
    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_pipeline_tools(mcp: FastMCP, client: Client) -> None:
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
            return json.dumps(pipelines, indent=2, default=str)
        except Exception as exc:
            logger.exception("list_pipelines failed")
            return f"Error listing pipelines: {exc}"

    @mcp.tool()
    def get_pipeline(pipeline_id: str) -> str:
        """Get the full configuration of a specific GlassFlow pipeline.

        Returns the complete V3 pipeline configuration as JSON, including
        sources, transforms, join, and sink definitions, resource limits,
        and metadata.

        Use this after list_pipelines to inspect a pipeline's detailed setup.

        Args:
            pipeline_id: The unique identifier of the pipeline.
        """
        try:
            p = client.get_pipeline(pipeline_id)
            return json.dumps(p.to_dict(), indent=2, default=str)
        except Exception as exc:
            logger.exception("get_pipeline failed for %s", pipeline_id)
            return f"Error getting pipeline {pipeline_id}: {exc}"

    @mcp.tool()
    def get_pipeline_health(pipeline_id: str) -> str:
        """Get the health and status of a GlassFlow pipeline.

        Returns the pipeline's overall status (Running, Stopped, Created,
        Failed, etc.) and component-level health information.

        Use this to check if a pipeline is running correctly.

        Args:
            pipeline_id: The unique identifier of the pipeline.
        """
        try:
            p = client.get_pipeline(pipeline_id)
            health = p.health()
            return json.dumps(health, indent=2, default=str)
        except Exception as exc:
            logger.exception("get_pipeline_health failed for %s", pipeline_id)
            return f"Error getting health for pipeline {pipeline_id}: {exc}"

    @mcp.tool()
    def create_pipeline(config: str) -> str:
        """Create a new GlassFlow pipeline from a V3 JSON configuration.

        IMPORTANT: Read the resource glassflow://docs/pipeline-v3-format
        for the complete V3 format reference with examples before building
        a config. Do NOT use the old format with "source"/"connector".

        Required V3 fields: version ("v3"), pipeline_id, sources array,
        and sink object. Optional: transforms, join, metadata, resources.

        Args:
            config: V3 pipeline configuration as a JSON string.
        """
        try:
            config_dict = json.loads(config)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON: {exc}"

        try:
            p = client.create_pipeline(pipeline_config=config_dict)
            return json.dumps(
                {"status": "created", "pipeline_id": p.pipeline_id},
                indent=2,
            )
        except Exception as exc:
            logger.exception("create_pipeline failed")
            return f"Error creating pipeline: {exc}"

    @mcp.tool()
    def stop_pipeline(pipeline_id: str) -> str:
        """Stop a running GlassFlow pipeline.

        The pipeline will stop consuming from Kafka and writing to ClickHouse.
        Messages produced while the pipeline is stopped will be consumed
        when the pipeline is resumed (Kafka offsets are preserved).

        Args:
            pipeline_id: The unique identifier of the pipeline to stop.
        """
        try:
            client.stop_pipeline(pipeline_id)
            return json.dumps({"status": "stopped", "pipeline_id": pipeline_id})
        except Exception as exc:
            logger.exception("stop_pipeline failed for %s", pipeline_id)
            return f"Error stopping pipeline {pipeline_id}: {exc}"

    @mcp.tool()
    def resume_pipeline(pipeline_id: str) -> str:
        """Resume a stopped GlassFlow pipeline.

        The pipeline will resume consuming from Kafka from where it left off.
        Any messages produced while the pipeline was stopped will be processed.

        Args:
            pipeline_id: The unique identifier of the pipeline to resume.
        """
        try:
            p = client.get_pipeline(pipeline_id)
            p.resume()
            return json.dumps({"status": "resuming", "pipeline_id": pipeline_id})
        except Exception as exc:
            logger.exception("resume_pipeline failed for %s", pipeline_id)
            return f"Error resuming pipeline {pipeline_id}: {exc}"

    @mcp.tool()
    def edit_pipeline(pipeline_id: str, config_patch: str) -> str:
        """Edit a stopped GlassFlow pipeline.

        The pipeline must be in Stopped state before editing. After a
        successful edit, the pipeline is automatically resumed.

        The config_patch is a JSON string with only the fields you want
        to change. Supported patch fields: name, sources, transforms,
        join, sink, resources. Fields not included in the patch remain
        unchanged.

        Read the resource glassflow://docs/pipeline-v3-format for the
        V3 field reference.

        Args:
            pipeline_id: The unique identifier of the pipeline to edit.
            config_patch: JSON string with the fields to update.
        """
        try:
            patch = json.loads(config_patch)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON in config_patch: {exc}"

        try:
            p = client.get_pipeline(pipeline_id)
            p.update(patch)
            return json.dumps(
                {"status": "edited", "pipeline_id": pipeline_id},
                indent=2,
            )
        except Exception as exc:
            logger.exception("edit_pipeline failed for %s", pipeline_id)
            return f"Error editing pipeline {pipeline_id}: {exc}"

    @mcp.tool()
    def delete_pipeline(pipeline_id: str) -> str:
        """Delete a GlassFlow pipeline.

        The pipeline must be stopped before deletion. This permanently
        removes the pipeline configuration and all associated resources.

        Args:
            pipeline_id: The unique identifier of the pipeline to delete.
        """
        try:
            client.delete_pipeline(pipeline_id)
            return json.dumps({"status": "deleted", "pipeline_id": pipeline_id})
        except Exception as exc:
            logger.exception("delete_pipeline failed for %s", pipeline_id)
            return f"Error deleting pipeline {pipeline_id}: {exc}"
