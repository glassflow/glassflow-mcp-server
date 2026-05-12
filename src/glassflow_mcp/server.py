"""GlassFlow MCP server — entry point and tool registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from glassflow_mcp.cluster import ClusterRegistry, register_cluster_tools
from glassflow_mcp.resources import register_resources
from glassflow_mcp.tools.diagnostics import register_diagnostics_tools
from glassflow_mcp.tools.pipeline import register_pipeline_tools

if TYPE_CHECKING:
    pass

_INSTRUCTIONS = (
    "Manage and diagnose GlassFlow streaming pipelines across multiple clusters.\n\n"
    "FIRST: If no cluster is connected, use connect_cluster to register a "
    "GlassFlow cluster. Ask the user for the GlassFlow API URL.\n\n"
    "PIPELINE CREATION: When the user asks to create a pipeline, ALWAYS ask "
    "them for the specific details first. You need: Kafka topic, broker "
    "addresses/credentials, ClickHouse host/credentials/table, event schema, "
    "and desired transforms. Do NOT use placeholder values.\n\n"
    "DIAGNOSTICS: Use diagnose_pipeline first for a complete snapshot, then "
    "drill deeper with query_pipeline_logs or query_pipeline_metrics.\n\n"
    "MULTI-CLUSTER: Use list_clusters to see connected clusters and "
    "switch_cluster to change the active one.\n\n"
    "Read the resource glassflow://docs/pipeline-v3-format for the V3 "
    "configuration format reference."
)


def create_server(
    registry: ClusterRegistry,
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> FastMCP:
    """Create and configure the MCP server with the given cluster registry.

    This factory keeps module-level imports side-effect-free so the
    server can be instantiated in tests with mock clients.
    """
    mcp = FastMCP(
        "GlassFlow Pipeline Manager",
        instructions=_INSTRUCTIONS,
        host=host,
        port=port,
    )

    register_resources(mcp)
    register_cluster_tools(mcp, registry)
    register_pipeline_tools(mcp, registry)
    register_diagnostics_tools(mcp, registry)

    return mcp


def main() -> None:
    """Run the MCP server with SSE transport."""
    from glassflow_mcp.config import Config

    config = Config.from_env()

    registry = ClusterRegistry()

    # If env vars are set, auto-connect a "default" cluster for
    # backwards compatibility (single-cluster deployments).
    if config.glassflow_api_url:
        registry.connect(
            name="default",
            api_url=config.glassflow_api_url,
            vm_url=config.victoriametrics_url,
            vl_url=config.victorialogs_url,
        )

    mcp = create_server(registry, host="0.0.0.0", port=config.mcp_port)
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
