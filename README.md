# GlassFlow MCP Server

[Model Context Protocol](https://modelcontextprotocol.io) server for managing and diagnosing [GlassFlow](https://glassflow.dev) streaming pipelines. Exposes pipeline CRUD, metrics queries, log search, and a composite diagnostic tool as MCP tools that AI agents (Claude Code, etc.) can call over SSE transport.

## Features

- **Multi-cluster** — connect to multiple GlassFlow deployments and switch between them at runtime
- **Pipeline management** — create, list, get, edit, stop, resume, delete pipelines
- **Diagnostics** — query throughput, latency, DLQ state, and error logs
- **`diagnose_pipeline`** — single-call diagnostic snapshot combining health, metrics, DLQ, and recent errors
- **V3 config reference** — MCP resource with the complete pipeline configuration format
- Uses the official [GlassFlow Python SDK](https://github.com/glassflow/glassflow-python-sdk)

## Quick start

### Local development

```bash
pip install -e .

# Option A: auto-connect a default cluster via env var
export GLASSFLOW_API_URL="http://localhost:8081"
python -m glassflow_mcp.server

# Option B: start with no cluster, connect at runtime via tools
python -m glassflow_mcp.server
```

### Connect Claude Code

```bash
claude mcp add --transport sse glassflow http://localhost:8080/sse
```

Start a new Claude Code session — the GlassFlow tools will appear automatically.

## Available tools

### Cluster management

Connect to one or more GlassFlow clusters and switch between them. All pipeline and diagnostic tools operate against the **active** cluster.

| Tool | Description |
|---|---|
| `connect_cluster` | Register a GlassFlow cluster by name + API URL (+ optional VM/VL URLs) |
| `list_clusters` | Show all connected clusters with active indicator |
| `switch_cluster` | Change the active cluster |
| `disconnect_cluster` | Remove a cluster connection |

**Example flow:**

```
You: "Connect to my staging cluster at http://staging-api:8081"
  → Agent calls: connect_cluster(name="staging", api_url="http://staging-api:8081")

You: "List my pipelines"
  → Agent calls: list_pipelines()  (uses staging)

You: "Now connect to production at http://prod-api:8081"
  → Agent calls: connect_cluster(name="production", api_url="http://prod-api:8081")

You: "Switch to production"
  → Agent calls: switch_cluster("production")

You: "List pipelines"
  → Agent calls: list_pipelines()  (now uses production)
```

If `GLASSFLOW_API_URL` is set as an env var, the server auto-connects a `default` cluster on startup for backwards compatibility.

### Pipeline management

| Tool | Description |
|---|---|
| `list_pipelines` | List all pipelines with status |
| `get_pipeline` | Get full V3 pipeline configuration |
| `get_pipeline_health` | Get pipeline health and status |
| `create_pipeline` | Create a new pipeline (V3 JSON config) |
| `edit_pipeline` | Edit a stopped pipeline |
| `stop_pipeline` | Stop a running pipeline |
| `resume_pipeline` | Resume a stopped pipeline |
| `delete_pipeline` | Delete a pipeline |

### Diagnostics

| Tool | Description |
|---|---|
| `diagnose_pipeline` | Complete diagnostic snapshot (health + metrics + DLQ + errors) |
| `query_pipeline_metrics` | Query specific metrics (throughput, latency, DLQ rate, bytes) |
| `query_custom_metric` | Custom PromQL query (restricted to `glassflow_gfm_*` metrics) |
| `query_pipeline_logs` | Search logs by pipeline, severity, and component |
| `get_pipeline_errors` | Recent ERROR/WARN logs for a pipeline |
| `get_dlq_state` | Dead-letter queue message count |

### Resources

| URI | Description |
|---|---|
| `glassflow://docs/pipeline-v3-format` | Complete V3 pipeline configuration reference with examples |

## Configuration

All configuration is via environment variables. These configure the **default** cluster that auto-connects on startup. Additional clusters can be added at runtime via `connect_cluster`.

| Variable | Default | Description |
|---|---|---|
| `GLASSFLOW_API_URL` | `http://glassflow-api....:8081` | GlassFlow REST API URL (default cluster) |
| `VICTORIAMETRICS_URL` | `http://victoria-metrics....:8428` | VictoriaMetrics URL (default cluster) |
| `VICTORIALOGS_URL` | `http://victoria-logs....:9428` | VictoriaLogs URL (default cluster) |
| `MCP_PORT` | `8080` | Port the SSE server listens on |

VictoriaMetrics and VictoriaLogs URLs are optional — metrics and log tools gracefully degrade when not configured for a cluster.

## Deployment

### Docker

```bash
docker build -t glassflow-mcp-server .
docker run -p 8080:8080 \
  -e GLASSFLOW_API_URL=http://your-glassflow-api:8081 \
  glassflow-mcp-server
```

### Kubernetes

Example manifests are provided in [`k8s/examples/`](k8s/examples/). Copy them, edit the `CHANGEME` values, and apply:

```bash
kubectl apply -f k8s/examples/deployment.yaml -f k8s/examples/service.yaml
```

Then connect via port-forward:

```bash
kubectl port-forward -n <namespace> svc/glassflow-mcp 8080:8080
claude mcp add --transport sse glassflow http://localhost:8080/sse
```

See [`k8s/README.md`](k8s/README.md) for full details including optional Ingress setup.

### PyPI

```bash
pip install mcp-server-glassflow
mcp-server-glassflow
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Lint
ruff check src/ tests/
ruff format --check src/ tests/
```

## License

[Apache 2.0](LICENSE)
