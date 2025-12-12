"""
Композитный инструмент для удобства.
"""
from typing import Dict, Any, Optional
from ..mcp_instance import mcp, TOOL_CALLS_TOTAL
from ..figma_client import figma_client, FigmaAPIError
from .styles_tool import _extract_styles_recursive

@mcp.tool
async def export_layout_and_styles(
    file_key: str, 
    node_ids: Optional[str] = None
) -> Dict[str, Any]:
    """
    Композитный инструмент: загружает макет из Figma И сразу извлекает стили.
    
    Args:
        file_key (str): Ключ Figma-файла.
        node_ids (str, optional): Список ID узлов через запятую.
    
    Returns:
        Dict[str, Any]: Объединенный результат.
    """
    if not file_key or not isinstance(file_key, str):
        raise ValueError("file_key обязателен")
    
    try:
        layout_data = await figma_client.get_file(file_key, node_ids)
    except FigmaAPIError as e:
        TOOL_CALLS_TOTAL.labels(tool_name="export_layout_and_styles", status="error").inc()
        raise
    
    raw_styles = _extract_styles_recursive(layout_data.get('document', {}))
    
    styles = {
        "colors": list(raw_styles['colors']),
        "text_styles": [dict(ts) for ts in raw_styles['text_styles']],
        "effects": list(raw_styles['effects']),
        "spacing": list(raw_styles['spacing']),
        "summary": {
            "total_colors": len(raw_styles['colors']),
            "total_text_styles": len(raw_styles['text_styles']),
            "total_effects": len(raw_styles['effects']),
            "layers_analyzed": raw_styles['layer_count']
        }
    }
    
    TOOL_CALLS_TOTAL.labels(tool_name="export_layout_and_styles", status="success").inc()
    
    return {
        "layout": {
            "name": layout_data.get("name"),
            "lastModified": layout_data.get("lastModified"),
            "thumbnailUrl": layout_data.get("thumbnailUrl"),
            "version": layout_data.get("version"),
        },
        "styles": styles,
        "summary": {
            "file": layout_data.get("name"),
            "styles_found": len(styles['colors']) + len(styles['text_styles']) + len(styles['effects']),
            "layers_analyzed": styles['summary']['layers_analyzed']
        }
    }