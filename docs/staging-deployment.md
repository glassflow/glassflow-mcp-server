# Staging Deployment Guide

Tracks all commands used to deploy the MCP server infrastructure on the DOKS staging cluster.

**Cluster context:** `do-ams3-staging-cluster`

---

## 1. VictoriaMetrics Single (metrics storage)

```bash
# Add Helm repo
helm repo add vm https://victoriametrics.github.io/helm-charts/
helm repo update vm

# Install VictoriaMetrics Single in observability namespace
helm install vmsingle vm/victoria-metrics-single \
  --kube-context do-ams3-staging-cluster \
  --namespace observability \
  --set server.retentionPeriod=7d \
  --set server.resources.requests.cpu=200m \
  --set server.resources.requests.memory=512Mi \
  --set server.resources.limits.cpu=1 \
  --set server.resources.limits.memory=1Gi \
  --set server.persistentVolume.size=20Gi
```

**In-cluster URL:** `http://vmsingle-victoria-metrics-single-server.observability.svc.cluster.local:8428`

**Endpoints:**
- Write (Prometheus remote_write): `/api/v1/write`
- PromQL query: `/api/v1/query?query=<promql>`
- PromQL range query: `/api/v1/query_range?query=<promql>&start=<ts>&end=<ts>&step=<step>`
- Label values: `/api/v1/label/__name__/values`

---

## 2. VictoriaLogs Single (log storage)

```bash
helm install vlogs vm/victoria-logs-single \
  --kube-context do-ams3-staging-cluster \
  --namespace observability \
  --set server.retentionPeriod=3d \
  --set server.resources.requests.cpu=100m \
  --set server.resources.requests.memory=256Mi \
  --set server.resources.limits.cpu=500m \
  --set server.resources.limits.memory=512Mi \
  --set server.persistentVolume.size=10Gi
```

**In-cluster URL:** `http://vlogs-victoria-logs-single-server.observability.svc.cluster.local:9428`

**Endpoints:**
- OTLP ingest: `/insert/opentelemetry/v1/logs`
- LogsQL query: `/select/logsql/query?query=<logsql>`
- Health: `/health`

---

## 3. Verify pods are running

```bash
kubectl --context do-ams3-staging-cluster get pods -n observability | grep -E "vmsingle|vlogs"
```

---

## 4. Verify connectivity from inside the cluster

```bash
API_POD=$(kubectl --context do-ams3-staging-cluster get pod -n glassflow -o name | grep api | head -1)

# VictoriaMetrics
kubectl --context do-ams3-staging-cluster exec -n glassflow $API_POD -- \
  wget -qO- "http://vmsingle-victoria-metrics-single-server.observability.svc.cluster.local:8428/api/v1/query?query=up"

# VictoriaLogs
kubectl --context do-ams3-staging-cluster exec -n glassflow $API_POD -- \
  wget -qO- "http://vlogs-victoria-logs-single-server.observability.svc.cluster.local:9428/health"
```

---

## 5. Update OTel Collector to fan out to VM + VL

```bash
# Export current configmap
kubectl --context do-ams3-staging-cluster get configmap -n glassflow <otel-configmap-name> -o yaml > /tmp/otel-cm.yaml
```

Add to the collector config YAML:

**Under `exporters:`:**
```yaml
  prometheusremotewrite/victoriametrics:
    endpoint: "http://vmsingle-victoria-metrics-single-server.observability.svc.cluster.local:8428/api/v1/write"
  otlphttp/victorialogs:
    endpoint: "http://vlogs-victoria-logs-single-server.observability.svc.cluster.local:9428/insert/opentelemetry"
    tls:
      insecure: true
```

**Under `service.pipelines.metrics.exporters:`** append:
```yaml
      - prometheusremotewrite/victoriametrics
```

**Under `service.pipelines.logs.exporters:`** append:
```yaml
      - otlphttp/victorialogs
```

Apply and restart:
```bash
kubectl --context do-ams3-staging-cluster apply -f /tmp/otel-cm-patched.yaml
kubectl --context do-ams3-staging-cluster rollout restart deployment/glassflow-otel-collector -n glassflow
```

---

## 6. Verify data flows to VictoriaMetrics

```bash
# Wait ~2 minutes for scrape, then check for GlassFlow metrics
kubectl --context do-ams3-staging-cluster exec -n glassflow $API_POD -- \
  wget -qO- "http://vmsingle-victoria-metrics-single-server.observability.svc.cluster.local:8428/api/v1/label/__name__/values" \
  | python3 -c "import json,sys; [print(m) for m in json.load(sys.stdin)['data'] if 'gf' in m.lower()]"
```

---

## 7. MCP Server deployment

TODO: fill in after building and pushing the Docker image.

```bash
# Build and push
# docker build -t <registry>/glassflow-mcp:latest .
# docker push <registry>/glassflow-mcp:latest

# Deploy
# kubectl --context do-ams3-staging-cluster apply -f k8s/deployment.yaml
# kubectl --context do-ams3-staging-cluster apply -f k8s/service.yaml
```

---

## Teardown

```bash
# Remove VictoriaMetrics
helm uninstall vmsingle --kube-context do-ams3-staging-cluster -n observability

# Remove VictoriaLogs
helm uninstall vlogs --kube-context do-ams3-staging-cluster -n observability

# Remove MCP server
# kubectl --context do-ams3-staging-cluster delete -f k8s/deployment.yaml
# kubectl --context do-ams3-staging-cluster delete -f k8s/service.yaml
```
