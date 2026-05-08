# GlassFlow MCP Server

MCP server for managing GlassFlow streaming pipelines. Exposes pipeline CRUD
operations, health checks, and DLQ inspection as MCP tools that AI agents
(Claude Code, etc.) can call over SSE transport.

## Quick start

```bash
# Install
pip install -e .

# Run (defaults to http://localhost:8080)
export GLASSFLOW_API_URL="http://glassflow-api.glassflow.svc.cluster.local:8081"
python -m glassflow_mcp.server
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `GLASSFLOW_API_URL` | `http://glassflow-api.glassflow.svc.cluster.local:8081` | GlassFlow API base URL |
| `VICTORIAMETRICS_URL` | `http://vmsingle-victoria-metrics-single-server.observability.svc.cluster.local:8428` | VictoriaMetrics URL (future) |
| `VICTORIALOGS_URL` | `http://vlogs-victoria-logs-single-server.observability.svc.cluster.local:9428` | VictoriaLogs URL (future) |
| `MCP_PORT` | `8080` | Port the MCP SSE server listens on |

## Available tools

| Tool | Description |
|---|---|
| `list_pipelines` | List all pipelines with status |
| `get_pipeline` | Get full pipeline configuration |
| `get_pipeline_health` | Get pipeline health and status |
| `create_pipeline` | Create a new pipeline (V3 config) |
| `stop_pipeline` | Stop a running pipeline |
| `resume_pipeline` | Resume a stopped pipeline |
| `delete_pipeline` | Delete a pipeline |
| `get_dlq_state` | Get dead-letter queue state |

## Docker

```bash
docker build -t glassflow-mcp:latest .
docker run -p 8080:8080 -e GLASSFLOW_API_URL=http://... glassflow-mcp:latest
```

## Kubernetes

```bash
kubectl apply -f k8s/
```

## Claude Code integration

Port-forward the service (if running in-cluster):

```bash
kubectl port-forward -n glassflow svc/glassflow-mcp 8080:8080
```

Register the MCP server with Claude Code CLI:

```bash
claude mcp add --transport sse glassflow http://localhost:8080/sse
```

Start a new Claude Code session — the GlassFlow tools should appear automatically.
