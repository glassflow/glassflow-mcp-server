"""Tests for configuration loading."""

from __future__ import annotations

import pytest

from glassflow_mcp.config import Config


class TestConfig:
    def test_defaults(self, monkeypatch):
        # Clear any env vars that might interfere
        for var in ("GLASSFLOW_API_URL", "VICTORIAMETRICS_URL", "VICTORIALOGS_URL", "MCP_PORT"):
            monkeypatch.delenv(var, raising=False)
        config = Config.from_env()
        assert "glassflow-api" in config.glassflow_api_url
        assert "victoria-metrics" in config.victoriametrics_url
        assert "victoria-logs" in config.victorialogs_url
        assert config.mcp_port == 8080

    def test_custom_env(self, monkeypatch):
        monkeypatch.setenv("GLASSFLOW_API_URL", "http://custom-api:9090")
        monkeypatch.setenv("MCP_PORT", "9999")
        config = Config.from_env()
        assert config.glassflow_api_url == "http://custom-api:9090"
        assert config.mcp_port == 9999

    def test_invalid_port(self, monkeypatch):
        monkeypatch.setenv("MCP_PORT", "not-a-number")
        with pytest.raises(ValueError):
            Config.from_env()

    def test_frozen(self):
        config = Config.from_env()
        with pytest.raises(AttributeError):
            config.mcp_port = 1234  # type: ignore[misc]
