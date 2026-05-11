# Kubernetes Deployment

Example manifests for deploying the GlassFlow MCP server in Kubernetes.

## Quick start

1. Copy the examples and edit the `CHANGEME` values:

```bash
cp k8s/examples/*.yaml k8s/
# Edit deployment.yaml — set your image, namespace, and backend URLs
# Edit service.yaml — set your namespace
# Edit ingress.yaml — set your domain (optional)
```

2. Apply:

```bash
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
```

3. Connect Claude Code via port-forward:

```bash
kubectl port-forward -n <namespace> svc/glassflow-mcp 8080:8080
claude mcp add --transport sse glassflow http://localhost:8080/sse
```

## Files

| File | Required | Description |
|---|---|---|
| `examples/deployment.yaml` | Yes | MCP server pod with env vars for backend URLs |
| `examples/service.yaml` | Yes | ClusterIP service for internal access |
| `examples/ingress.yaml` | No | Ingress for external access (requires auth!) |

## Configuration

All configuration is via environment variables in `deployment.yaml`:

| Variable | Required | Description |
|---|---|---|
| `GLASSFLOW_API_URL` | Yes | GlassFlow REST API URL |
| `VICTORIAMETRICS_URL` | No | VictoriaMetrics URL for metrics queries |
| `VICTORIALOGS_URL` | No | VictoriaLogs URL for log queries |
| `MCP_PORT` | No | Server port (default: 8080) |

## Security

The MCP server has **no built-in authentication**. If you expose it
via Ingress, protect it with one of:

- [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/applications/configure-apps/)
- [OAuth2 Proxy](https://oauth2-proxy.github.io/oauth2-proxy/)
- Ingress basic auth annotations
- Network policies restricting access to trusted IPs
