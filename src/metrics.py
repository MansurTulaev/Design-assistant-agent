"""
Prometheus метрики сервера.
"""
from prometheus_client import CollectorRegistry, generate_latest
from .mcp_instance import TOOL_CALLS_TOTAL, TOOL_CALL_DURATION, FIGMA_API_CALLS

app_registry = CollectorRegistry()
app_registry.register(TOOL_CALLS_TOTAL)
app_registry.register(TOOL_CALL_DURATION)
app_registry.register(FIGMA_API_CALLS)

def get_metrics():
    """Возвращает метрики в формате Prometheus."""
    return generate_latest(app_registry)