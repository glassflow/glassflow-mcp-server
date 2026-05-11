"""GlassFlow MCP server — entry point and tool registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from glassflow_mcp.resources import register_resources
from glassflow_mcp.tools.diagnostics import register_diagnostics_tools
from glassflow_mcp.tools.pipeline import register_pipeline_tools

if TYPE_CHECKING:
    from glassflow.etl import Client

    from glassflow_mcp.vl_client import VLClient
    from glassflow_mcp.vm_client import VMClient

_INSTRUCTIONS = (
    "Manage and diagnose GlassFlow streaming pipelines. "
    "Use list_pipelines to see all pipelines, get_pipeline_health "
    "to check status, and create_pipeline to create new ones.\n\n"
    "IMPORTANT: When the user asks to create a pipeline, ALWAYS ask "
    "them for the specific details first before calling create_pipeline. "
    "You need to know: the Kafka topic name, Kafka broker addresses and "
    "credentials, the ClickHouse host/credentials/table name, the event "
    "schema (field names and types), and what transforms they want "
    "(dedup, filter, stateless). Do NOT use placeholder or example "
    "values from the documentation — always use real values provided "
    "by the user.\n\n"
    "For diagnosing pipeline issues, use diagnose_pipeline first to "
    "get a complete snapshot, then drill deeper with query_pipeline_logs "
    "or query_pipeline_metrics as needed.\n\n"
    "Read the resource glassflow://docs/pipeline-v3-format for the "
    "V3 configuration format reference."
)


def create_server(
    gf_client: Client,
    vm_client: VMClient,
    vl_client: VLClient,
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> FastMCP:
    """Create and configure the MCP server with the given backends.

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
    register_pipeline_tools(mcp, gf_client)
    register_diagnostics_tools(mcp, gf_client, vm_client, vl_client)

    return mcp


def main() -> None:
    """Run the MCP server with SSE transport."""
    from glassflow.etl import Client

    from glassflow_mcp.config import Config
    from glassflow_mcp.vl_client import VLClient
    from glassflow_mcp.vm_client import VMClient

    config = Config.from_env()

    gf_client = Client(host=config.glassflow_api_url)
    gf_client.disable_usagestats()
    vm = VMClient(base_url=config.victoriametrics_url)
    vl = VLClient(base_url=config.victorialogs_url)

    mcp = create_server(gf_client, vm, vl, host="0.0.0.0", port=config.mcp_port)
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
