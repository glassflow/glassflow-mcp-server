"""Environment-based configuration for the GlassFlow MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Immutable server configuration loaded from environment variables."""

    glassflow_api_url: str
    victoriametrics_url: str
    victorialogs_url: str
    mcp_port: int

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            glassflow_api_url=os.environ.get(
                "GLASSFLOW_API_URL",
                "http://glassflow-api.glassflow.svc.cluster.local:8081",
            ),
            victoriametrics_url=os.environ.get(
                "VICTORIAMETRICS_URL",
                "http://glassflow-victoria-metrics-single-server.glassflow.svc.cluster.local:8428",
            ),
            victorialogs_url=os.environ.get(
                "VICTORIALOGS_URL",
                "http://glassflow-victoria-logs-single-server.glassflow.svc.cluster.local:9428",
            ),
            mcp_port=int(os.environ.get("MCP_PORT", "8080")),
        )
