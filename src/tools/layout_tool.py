"""
Инструмент для выгрузки макетов из Figma.
"""
import json
from typing import Dict, Any, Optional
from ..mcp_instance import mcp, TOOL_CALLS_TOTAL, TOOL_CALL_DURATION
from ..figma_client import figma_client, FigmaAPIError

@mcp.tool
async def export_figma_layout(
    file_key: str, 
    node_ids: Optional[str] = None,
    include_images: bool = False,
    image_format: str = "png"
) -> Dict[str, Any]:
    """
    Загружает структуру макета из Figma.
    
    Args:
        file_key (str): Ключ Figma-файла.
        node_ids (str, optional): Список ID узлов через запятую.
        include_images (bool): Включать ссылки на изображения.
        image_format (str): Формат изображений.
    
    Returns:
        Dict[str, Any]: Ответ Figma Files API.
    """
    import time
    start_time = time.time()
    
    if not file_key or not isinstance(file_key, str):
        raise ValueError("file_key обязателен и должен быть строкой")
    
    try:
        file_data = await figma_client.get_file(file_key, node_ids)
        
        result = {
            "name": file_data.get("name", "Unnamed"),
            "document": file_data.get("document", {}),
            "lastModified": file_data.get("lastModified", ""),
            "thumbnailUrl": file_data.get("thumbnailUrl", ""),
            "version": file_data.get("version", "")
        }
        
        duration = time.time() - start_time
        TOOL_CALL_DURATION.labels(tool_name="export_figma_layout").observe(duration)
        TOOL_CALLS_TOTAL.labels(tool_name="export_figma_layout", status="success").inc()
        
        return result
        
    except Exception as e:
        TOOL_CALLS_TOTAL.labels(tool_name="export_figma_layout", status="error").inc()
        raise FigmaAPIError(f"Ошибка при выгрузке макета: {str(e)}")

@mcp.tool
async def get_frame_by_name(file_key: str, frame_name: str) -> Dict[str, Any]:
    """Находит фрейм по имени в файле Figma."""
    if not file_key or not frame_name:
        raise ValueError("file_key и frame_name обязательны")
    
    try:
        file_data = await figma_client.get_file(file_key)
        
        def find_frame(node, name):
            if node.get("name") == name and node.get("type") == "FRAME":
                return node
            
            for child in node.get("children", []):
                result = find_frame(child, name)
                if result:
                    return result
            
            return None
        
        document = file_data.get("document", {})
        frame = find_frame(document, frame_name)
        
        TOOL_CALLS_TOTAL.labels(tool_name="get_frame_by_name", status="success").inc()
        
        return {
            "found": frame is not None,
            "frame": frame or {},
            "file_name": file_data.get("name", "")
        }
        
    except Exception as e:
        TOOL_CALLS_TOTAL.labels(tool_name="get_frame_by_name", status="error").inc()
        raise