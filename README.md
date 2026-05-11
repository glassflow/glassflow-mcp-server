# GlassFlow MCP Server

[Model Context Protocol](https://modelcontextprotocol.io) server for managing and diagnosing [GlassFlow](https://glassflow.dev) streaming pipelines. Exposes pipeline CRUD, metrics queries, log search, and a composite diagnostic tool as MCP tools that AI agents (Claude Code, etc.) can call over SSE transport.

## Features

- **Pipeline management** — create, list, get, edit, stop, resume, delete pipelines
- **Diagnostics** — query throughput, latency, DLQ state, and error logs
- **`diagnose_pipeline`** — single-call diagnostic snapshot combining health, metrics, DLQ, and recent errors
- **V3 config reference** — MCP resource with the complete pipeline configuration format
- Uses the official [GlassFlow Python SDK](https://github.com/glassflow/glassflow-python-sdk)

## Quick start

### Local development

```bash
pip install -e .

export GLASSFLOW_API_URL="http://localhost:8081"  # or port-forward to your cluster
python -m glassflow_mcp.server
```

### Connect Claude Code

```bash
claude mcp add --transport sse glassflow http://localhost:8080/sse
```

Start a new Claude Code session — the GlassFlow tools will appear automatically.

## Available tools

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

All configuration is via environment variables:

| Variable | Default | Description |
|---|---|---|
| `GLASSFLOW_API_URL` | `http://glassflow-api....:8081` | GlassFlow REST API URL |
| `VICTORIAMETRICS_URL` | `http://victoria-metrics....:8428` | VictoriaMetrics URL for metrics queries |
| `VICTORIALOGS_URL` | `http://victoria-logs....:9428` | VictoriaLogs URL for log queries |
| `MCP_PORT` | `8080` | Port the SSE server listens on |

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

[MIT](LICENSE)
