"""
Main file MCP Server Figma.
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.mcp_instance import mcp
from src.config import config
from src.metrics import get_metrics


from src.tools.layout_tool import export_figma_layout, get_frame_by_name
from src.tools.ds_tool import scan_design_system, find_component_by_name
from src.tools.styles_tool import extract_styles_from_layout, export_styles_to_css
from src.tools.composite_tool import export_layout_and_styles


logging.basicConfig(
    level=getattr(logging, config.server.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Health check endpoint
@mcp.resource("health://check")
async def health_check() -> str:
    """Health check endpoint"""
    import json
    return json.dumps({
        "status": "healthy",
        "service": "figma-mcp-server",
        "version": "1.0.0"
    })


@mcp.resource("metrics://prometheus")
async def metrics_endpoint() -> str:
    """Returns metrics Prometheus."""
    return get_metrics().decode('utf-8')

def main():
    """Start MCP server."""
    logger.info(f"Starting Figma MCP Server v1.0.0")
    logger.info(f"Host: {config.server.host}, Port: {config.server.port}")
    logger.info("Starting server...")
    mcp.run(
        transport="streamable-http",
        host=config.server.host,
        port=config.server.port
    )
if __name__ == "__main__":
    main()