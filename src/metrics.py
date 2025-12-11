import os
import logging
from prometheus_client import Counter, Histogram, Gauge

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("mcp_figma")

# Prometheus метрики
TOOL_CALLS_TOTAL = Counter(
    'mcp_figma_tool_calls_total',
    'Total number of tool calls',
    ['tool_name', 'status']
)

FIGMA_API_CALLS_TOTAL = Counter(
    'mcp_figma_figma_api_calls_total',
    'Total number of Figma API calls',
    ['endpoint', 'status']
)

TOOL_DURATION_SECONDS = Histogram(
    'mcp_figma_tool_duration_seconds',
    'Tool execution duration in seconds',
    ['tool_name']
)

COMPONENTS_SCANNED = Gauge(
    'mcp_figma_components_scanned',
    'Number of components scanned from design system'
)

# Защитные лимиты
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "50000000"))  # 50 MB
MAX_COMPONENTS = int(os.getenv("MAX_COMPONENTS", "1000"))
FIGMA_API_TIMEOUT = int(os.getenv("FIGMA_API_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))