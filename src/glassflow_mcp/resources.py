"""MCP resources providing reference documentation to AI agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

PIPELINE_CONFIG_REFERENCE = """\
# GlassFlow Pipeline V3 Configuration Reference

Full docs: https://docs.glassflow.dev/configuration/pipeline-config-reference

## Root Structure

```yaml
version: "v3"                    # required
pipeline_id: "my-pipeline"       # required, min 5 chars
name: "My Pipeline"              # optional
sources: [...]                   # required, at least one
sink: {...}                      # required
transforms: [...]                # optional
join: {...}                      # optional
metadata: {tags: [...]}          # optional
resources: {...}                 # optional
```

## Sources

### Kafka Source

```yaml
sources:
  - type: "kafka"
    source_id: "my-topic"                    # unique id, typically = topic name
    topic: "my-topic"                        # Kafka topic name
    consumer_group_initial_offset: "earliest" # or "latest" (default)
    connection_params:
      brokers: ["kafka:9092"]
      protocol: "SASL_PLAINTEXT"             # PLAINTEXT | SASL_PLAINTEXT | SSL | SASL_SSL
      mechanism: "PLAIN"                     # PLAIN | SCRAM-SHA-256 | SCRAM-SHA-512
      username: "user"
      password: "pass"
      # Optional TLS:
      # root_ca: "..."
      # skip_tls_verification: false
      # Optional Kerberos:
      # kerberos_service_name: "kafka"
      # kerberos_realm: "EXAMPLE.COM"
      # kerberos_keytab: "base64..."
      # kerberos_config: "base64..."
    schema_fields:                           # required for Kafka sources
      - name: "id"
        type: "string"
      - name: "user_id"
        type: "int"
      - name: "amount"
        type: "float"
      - name: "metadata.source"              # dot notation for nested fields
        type: "string"
```

### OTLP Sources (no connection_params or schema_fields needed)

```yaml
# Logs
sources:
  - type: "otlp.logs"
    source_id: "my-logs"

# Traces
sources:
  - type: "otlp.traces"
    source_id: "my-traces"

# Metrics
sources:
  - type: "otlp.metrics"
    source_id: "my-metrics"
```

## Transforms

Array of processing steps applied per source. Order matters.

### Deduplication

```yaml
transforms:
  - type: "dedup"
    source_id: "my-topic"
    config:
      key: "id"              # field to deduplicate on
      time_window: "1h"      # window: "30s", "1m", "1h", "24h"
```

### Filter

Keeps events where the expression is true, drops the rest.

```yaml
transforms:
  - type: "filter"
    source_id: "my-topic"
    config:
      expression: "amount > 100.0"    # events matching this are KEPT
```

### Stateless Transformation

Compute derived fields using expressions.

```yaml
transforms:
  - type: "stateless"
    source_id: "my-topic"
    config:
      transforms:
        - expression: "id"
          output_name: "id"
          output_type: "string"
        - expression: "int(amount * 100)"
          output_name: "amount_cents"
          output_type: "int"
        - expression: 'first_name + " " + last_name'
          output_name: "full_name"
          output_type: "string"
```

### Combining Transforms

Multiple transforms can be chained for the same source:

```yaml
transforms:
  - type: "dedup"
    source_id: "my-topic"
    config:
      key: "id"
      time_window: "1h"
  - type: "filter"
    source_id: "my-topic"
    config:
      expression: "amount > 100.0"
  - type: "stateless"
    source_id: "my-topic"
    config:
      transforms:
        - expression: "id"
          output_name: "id"
          output_type: "string"
        - expression: "int(amount * 100)"
          output_name: "amount_cents"
          output_type: "int"
```

## Join

Temporal join combines events from two sources by a shared key within
a time window.

```yaml
join:
  enabled: true
  type: "temporal"
  left_source:
    source_id: "orders"
    key: "user_id"              # join key field
    time_window: "30s"
  right_source:
    source_id: "users"
    key: "user_id"
    time_window: "30s"
  output_fields:                # fields to include in joined output
    - source_id: "orders"
      name: "order_id"
    - source_id: "orders"
      name: "amount"
    - source_id: "users"
      name: "user_name"
      output_name: "customer_name"   # optional rename
```

When using join, provide both topics in the sources array:

```yaml
sources:
  - type: "kafka"
    source_id: "orders"
    topic: "orders"
    connection_params: {...}
    schema_fields: [...]
  - type: "kafka"
    source_id: "users"
    topic: "users"
    connection_params: {...}
    schema_fields: [...]
```

## Sink (ClickHouse)

```yaml
sink:
  type: "clickhouse"
  connection_params:
    host: "clickhouse.svc.cluster.local"
    port: "9000"
    http_port: "8123"               # optional
    database: "default"
    username: "default"
    password: "plaintext-password"  # NOT base64 encoded
    secure: false
    # skip_certificate_verification: false
  table: "my_table"
  max_batch_size: 1000              # default: 1000
  max_delay_time: "5s"              # default: "60s"
  mapping:                          # maps source fields to ClickHouse columns
    - name: "id"
      column_name: "id"
      column_type: "String"
    - name: "amount"
      column_name: "amount"
      column_type: "Float64"
    - name: "amount_cents"
      column_name: "amount_cents"
      column_type: "Int64"
    - name: "ts"
      column_name: "event_timestamp"
      column_type: "DateTime"
```

Supported ClickHouse types: String, Int32, Int64, UInt32, UInt64,
Float32, Float64, DateTime, UUID, LowCardinality(String), Array(String),
Map(String, String).

## Resources

Control Kubernetes resource allocation per component.

```yaml
resources:
  nats:
    stream:
      max_age: "24h"       # immutable after creation
      max_bytes: "10Gi"    # immutable after creation
  sources:
    - source_id: "my-topic"
      replicas: 1
      requests: {cpu: "100m", memory: "128Mi"}
      limits: {cpu: "1500m", memory: "1.5Gi"}
  transform:
    - source_id: "my-topic"
      replicas: 1
      storage: {size: "10Gi"}    # only when dedup is enabled
      requests: {cpu: "100m", memory: "128Mi"}
      limits: {cpu: "1500m", memory: "1.5Gi"}
  sink:
    replicas: 1
    requests: {cpu: "100m", memory: "128Mi"}
    limits: {cpu: "1500m", memory: "1.5Gi"}
```

## Complete Examples

### Simple Kafka to ClickHouse (no transforms)

```json
{
  "version": "v3",
  "pipeline_id": "simple-ingest",
  "name": "Simple Kafka Ingestion",
  "sources": [{
    "type": "kafka",
    "source_id": "events",
    "topic": "events",
    "connection_params": {
      "brokers": ["kafka:9092"],
      "mechanism": "PLAIN",
      "protocol": "SASL_PLAINTEXT",
      "username": "glassflow",
      "password": "secret"
    },
    "schema_fields": [
      {"name": "id", "type": "string"},
      {"name": "value", "type": "float"},
      {"name": "ts", "type": "int"}
    ]
  }],
  "sink": {
    "type": "clickhouse",
    "connection_params": {
      "host": "clickhouse",
      "port": "9000",
      "http_port": "8123",
      "database": "default",
      "username": "default",
      "password": "",
      "secure": false
    },
    "table": "events",
    "max_batch_size": 1000,
    "max_delay_time": "5s",
    "mapping": [
      {"name": "id", "column_name": "id", "column_type": "String"},
      {"name": "value", "column_name": "value", "column_type": "Float64"},
      {"name": "ts", "column_name": "ts", "column_type": "Int64"}
    ]
  }
}
```

### With Dedup + Filter + Stateless Transform

```json
{
  "version": "v3",
  "pipeline_id": "full-transform",
  "name": "Full Transform Pipeline",
  "sources": [{
    "type": "kafka",
    "source_id": "orders",
    "topic": "orders",
    "connection_params": {
      "brokers": ["kafka:9092"],
      "mechanism": "PLAIN",
      "protocol": "SASL_PLAINTEXT",
      "username": "glassflow",
      "password": "secret"
    },
    "schema_fields": [
      {"name": "order_id", "type": "string"},
      {"name": "amount", "type": "float"},
      {"name": "ts", "type": "int"}
    ]
  }],
  "transforms": [
    {
      "type": "dedup",
      "source_id": "orders",
      "config": {"key": "order_id", "time_window": "1h"}
    },
    {
      "type": "filter",
      "source_id": "orders",
      "config": {"expression": "amount > 0"}
    },
    {
      "type": "stateless",
      "source_id": "orders",
      "config": {
        "transforms": [
          {"expression": "order_id", "output_name": "order_id", "output_type": "string"},
          {"expression": "amount", "output_name": "amount", "output_type": "float"},
          {"expression": "int(amount * 100)", "output_name": "amount_cents", "output_type": "int"},
          {"expression": "ts", "output_name": "ts", "output_type": "int"}
        ]
      }
    }
  ],
  "sink": {
    "type": "clickhouse",
    "connection_params": {
      "host": "clickhouse",
      "port": "9000",
      "http_port": "8123",
      "database": "default",
      "username": "default",
      "password": "",
      "secure": false
    },
    "table": "orders_processed",
    "max_batch_size": 1000,
    "max_delay_time": "5s",
    "mapping": [
      {"name": "order_id", "column_name": "order_id", "column_type": "String"},
      {"name": "amount", "column_name": "amount", "column_type": "Float64"},
      {"name": "amount_cents", "column_name": "amount_cents", "column_type": "Int64"},
      {"name": "ts", "column_name": "ts", "column_type": "Int64"}
    ]
  }
}
```

### OTLP Logs Pipeline

```json
{
  "version": "v3",
  "pipeline_id": "otlp-logs",
  "name": "OTLP Logs Ingestion",
  "sources": [{"type": "otlp.logs", "source_id": "app-logs"}],
  "sink": {
    "type": "clickhouse",
    "connection_params": {
      "host": "clickhouse",
      "port": "9000",
      "http_port": "8123",
      "database": "default",
      "username": "default",
      "password": "",
      "secure": false
    },
    "table": "logs",
    "max_batch_size": 1000,
    "max_delay_time": "5s",
    "mapping": [
      {"name": "timestamp", "column_name": "timestamp", "column_type": "String"},
      {"name": "severity_text", "column_name": "severity_text", "column_type": "String"},
      {"name": "body", "column_name": "body", "column_type": "String"},
      {"name": "scope_name", "column_name": "scope_name", "column_type": "String"}
    ]
  }
}
```
"""


def register_resources(mcp: FastMCP) -> None:
    """Register documentation resources on the MCP server."""

    @mcp.resource("glassflow://docs/pipeline-v3-format")
    def pipeline_v3_reference() -> str:
        """GlassFlow Pipeline V3 configuration reference.

        Complete field reference with examples for all source types
        (Kafka, OTLP), transform types (dedup, filter, stateless),
        temporal joins, ClickHouse sink mapping, and resource allocation.

        Read this before creating or modifying pipelines.
        """
        return PIPELINE_CONFIG_REFERENCE
