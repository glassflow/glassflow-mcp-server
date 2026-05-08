"""GlassFlow MCP server — entry point and tool registration."""

from __future__ import annotations

from glassflow.etl import Client
from mcp.server.fastmcp import FastMCP

from glassflow_mcp.config import Config
from glassflow_mcp.resources import register_resources
from glassflow_mcp.tools.diagnostics import register_diagnostics_tools
from glassflow_mcp.tools.pipeline import register_pipeline_tools

config = Config.from_env()

mcp = FastMCP(
    "GlassFlow Pipeline Manager",
    instructions=(
        "Manage and diagnose GlassFlow streaming pipelines. "
        "Use list_pipelines to see all pipelines, get_pipeline_health "
        "to check status, and create_pipeline to create new ones."
    ),
    host="0.0.0.0",
    port=config.mcp_port,
)

client = Client(host=config.glassflow_api_url)
client.disable_usagestats()

register_resources(mcp)
register_pipeline_tools(mcp, client)
register_diagnostics_tools(mcp, client)


def main() -> None:
    """Run the MCP server with SSE transport."""
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
