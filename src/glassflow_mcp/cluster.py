"""Cluster registry for multi-cluster support.

Manages connections to multiple GlassFlow deployments and tracks
which one is currently active. All pipeline and diagnostic tools
query the registry for the active cluster's clients.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from glassflow.etl import Client
    from mcp.server.fastmcp import FastMCP

    from glassflow_mcp.vl_client import VLClient
    from glassflow_mcp.vm_client import VMClient

logger = logging.getLogger(__name__)


@dataclass
class ClusterConnection:
    """A connection to a single GlassFlow cluster."""

    name: str
    api_url: str
    gf_client: Client
    vm_client: VMClient | None = None
    vl_client: VLClient | None = None
    vm_url: str = ""
    vl_url: str = ""


class ClusterRegistry:
    """Manages connections to multiple GlassFlow clusters.

    Thread-safety: not required — MCP tools execute sequentially
    within a single session.
    """

    def __init__(self) -> None:
        self._clusters: dict[str, ClusterConnection] = {}
        self._active_name: str | None = None

    def connect(
        self,
        name: str,
        api_url: str,
        vm_url: str = "",
        vl_url: str = "",
    ) -> ClusterConnection:
        """Register a new cluster connection.

        Creates SDK and observability clients. Sets as active if this
        is the first cluster.
        """
        from glassflow.etl import Client

        from glassflow_mcp.vl_client import VLClient
        from glassflow_mcp.vm_client import VMClient

        gf = Client(host=api_url)
        gf.disable_usagestats()

        vm = VMClient(base_url=vm_url) if vm_url else None
        vl = VLClient(base_url=vl_url) if vl_url else None

        conn = ClusterConnection(
            name=name,
            api_url=api_url,
            gf_client=gf,
            vm_client=vm,
            vl_client=vl,
            vm_url=vm_url,
            vl_url=vl_url,
        )
        self._clusters[name] = conn

        if self._active_name is None:
            self._active_name = name
            logger.info("Connected to cluster %r (active)", name)
        else:
            logger.info("Connected to cluster %r", name)

        return conn

    def switch(self, name: str) -> ClusterConnection:
        """Switch the active cluster. Raises KeyError if not found."""
        if name not in self._clusters:
            raise KeyError(
                f"Cluster '{name}' not found. "
                f"Available: {', '.join(sorted(self._clusters)) or '(none)'}"
            )
        self._active_name = name
        logger.info("Switched active cluster to %r", name)
        return self._clusters[name]

    def disconnect(self, name: str) -> None:
        """Remove a cluster connection."""
        if name not in self._clusters:
            raise KeyError(f"Cluster '{name}' not found")
        conn = self._clusters.pop(name)
        if conn.vm_client:
            conn.vm_client.close()
        if conn.vl_client:
            conn.vl_client.close()
        if self._active_name == name:
            self._active_name = next(iter(self._clusters), None)
        logger.info("Disconnected cluster %r", name)

    def active(self) -> ClusterConnection:
        """Return the active cluster connection.

        Raises RuntimeError if no cluster is connected.
        """
        if self._active_name is None or self._active_name not in self._clusters:
            raise RuntimeError(
                "No cluster connected. Use connect_cluster to register a GlassFlow cluster first."
            )
        return self._clusters[self._active_name]

    def list(self) -> list[dict[str, Any]]:
        """Return a summary of all registered clusters."""
        return [
            {
                "name": conn.name,
                "api_url": conn.api_url,
                "vm_url": conn.vm_url or "(not configured)",
                "vl_url": conn.vl_url or "(not configured)",
                "active": conn.name == self._active_name,
            }
            for conn in self._clusters.values()
        ]

    def is_connected(self) -> bool:
        return bool(self._clusters)


def register_cluster_tools(mcp: FastMCP, registry: ClusterRegistry) -> None:
    """Register cluster management tools on the MCP server."""

    @mcp.tool()
    def connect_cluster(
        name: str,
        api_url: str,
        vm_url: str = "",
        vl_url: str = "",
    ) -> str:
        """Connect to a GlassFlow cluster.

        Registers a new cluster connection by name. The first cluster
        connected becomes the active cluster. All pipeline and diagnostic
        tools operate against the active cluster.

        Ask the user for the GlassFlow API URL. VictoriaMetrics and
        VictoriaLogs URLs are optional — metrics and log tools will be
        unavailable for clusters without them.

        Args:
            name: A short name for this cluster (e.g., "staging", "production").
            api_url: GlassFlow REST API URL (e.g., "http://glassflow-api:8081").
            vm_url: VictoriaMetrics URL (optional, for metrics tools).
            vl_url: VictoriaLogs URL (optional, for log tools).
        """
        try:
            conn = registry.connect(name, api_url, vm_url, vl_url)
            return json.dumps(
                {
                    "status": "connected",
                    "cluster": conn.name,
                    "active": conn.name == registry._active_name,
                },
                indent=2,
            )
        except Exception as exc:
            logger.exception("connect_cluster failed for %r", name)
            return f"Error connecting to cluster '{name}': {exc}"

    @mcp.tool()
    def list_clusters() -> str:
        """List all registered GlassFlow cluster connections.

        Shows each cluster's name, URLs, and which one is currently active.
        Use this to see available clusters before switching.
        """
        clusters = registry.list()
        if not clusters:
            return json.dumps(
                {"clusters": [], "message": "No clusters connected. Use connect_cluster first."},
                indent=2,
            )
        return json.dumps({"clusters": clusters}, indent=2)

    @mcp.tool()
    def switch_cluster(name: str) -> str:
        """Switch the active GlassFlow cluster.

        All subsequent pipeline and diagnostic tool calls will operate
        against the newly active cluster.

        Args:
            name: Name of a previously connected cluster.
        """
        try:
            registry.switch(name)
            return json.dumps({"status": "switched", "active_cluster": name})
        except KeyError as exc:
            return str(exc)

    @mcp.tool()
    def disconnect_cluster(name: str) -> str:
        """Disconnect from a GlassFlow cluster.

        Removes the cluster connection. If the disconnected cluster was
        active, the next available cluster becomes active.

        Args:
            name: Name of the cluster to disconnect.
        """
        try:
            registry.disconnect(name)
            active = registry._active_name
            return json.dumps(
                {
                    "status": "disconnected",
                    "cluster": name,
                    "active_cluster": active,
                },
                indent=2,
            )
        except KeyError as exc:
            return str(exc)
