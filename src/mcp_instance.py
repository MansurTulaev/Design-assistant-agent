"""
Единый экземпляр FastMCP для всего сервера.
"""
import os
from fastmcp import FastMCP
from prometheus_client import Counter, Histogram

# Создаем единый экземпляр FastMCP
mcp = FastMCP("Figma Design System Server")

# Prometheus метрики
TOOL_CALLS_TOTAL = Counter(
    "tool_calls_total",
    "Total number of tool calls",
    ["tool_name", "status"]
)

TOOL_CALL_DURATION = Histogram(
    "tool_call_duration_seconds",
    "Duration of tool calls",
    ["tool_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

FIGMA_API_CALLS = Counter(
    "figma_api_calls_total",
    "Total number of Figma API calls",
    ["endpoint", "status"]
)