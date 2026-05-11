# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in the GlassFlow MCP Server, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email **security@glassflow.dev** with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge your report within 48 hours and aim to release a fix within 7 days for critical issues.

## Scope

This policy covers:

- The GlassFlow MCP Server codebase (`src/`)
- The Docker image and Kubernetes manifests (`k8s/examples/`)
- Dependencies listed in `pyproject.toml`

## Known Security Considerations

- The MCP server has **no built-in authentication**. When exposed publicly (via Ingress), protect it with an external auth layer (Cloudflare Access, OAuth2 Proxy, etc.).
- The `query_custom_metric` tool restricts PromQL queries to `glassflow_gfm_*` metrics only.
- All user inputs in LogsQL/PromQL queries are validated against a safe character set to prevent injection.
