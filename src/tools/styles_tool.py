"""
Инструмент для извлечения стилей из JSON-структуры макета Figma.
"""
from typing import Dict, Any, List
from ..mcp_instance import mcp, TOOL_CALLS_TOTAL

def _extract_styles_recursive(node: Dict, result: Dict = None) -> Dict:
    """Рекурсивно обходит дерево узлов Figma и извлекает стили."""
    if result is None:
        result = {
            'colors': set(),
            'text_styles': set(),
            'effects': set(),
            'spacing': set(),
            'layer_count': 0
        }
    
    result['layer_count'] += 1
    
    # Извлекаем цвета
    if 'fills' in node and isinstance(node['fills'], list):
        for fill in node['fills']:
            if fill.get('type') == 'SOLID' and 'color' in fill:
                color = fill['color']
                rgba = (
                    f"rgba("
                    f"{int(color.get('r', 0) * 255)}, "
                    f"{int(color.get('g', 0) * 255)}, "
                    f"{int(color.get('b', 0) * 255)}, "
                    f"{color.get('a', 1)}"
                    f")"
                )
                result['colors'].add(rgla)
    
    # Извлекаем стили текста
    if 'style' in node and node.get('type') == 'TEXT':
        text_style = {
            'font_family': node['style'].get('fontFamily', ''),
            'font_size': node['style'].get('fontSize', 0),
            'font_weight': node['style'].get('fontWeight', 400),
            'line_height': node['style'].get('lineHeightPx', 0),
        }
        result['text_styles'].add(frozenset(text_style.items()))
    
    # Извлекаем эффекты
    if 'effects' in node and isinstance(node['effects'], list):
        for effect in node['effects']:
            if effect.get('type') == 'DROP_SHADOW':
                shadow = (
                    f"{effect.get('offset', {}).get('x', 0)}px "
                    f"{effect.get('offset', {}).get('y', 0)}px "
                    f"{effect.get('radius', 0)}px "
                    f"rgba({int(effect.get('color', {}).get('r', 0) * 255)}, "
                    f"{int(effect.get('color', {}).get('g', 0) * 255)}, "
                    f"{int(effect.get('color', {}).get('b', 0) * 255)}, "
                    f"{effect.get('color', {}).get('a', 1)})"
                )
                result['effects'].add(shadow)
    
    # Извлекаем размеры
    if 'absoluteBoundingBox' in node:
        bbox = node['absoluteBoundingBox']
        if 'width' in bbox:
            result['spacing'].add(f"width: {bbox['width']}px")
        if 'height' in bbox:
            result['spacing'].add(f"height: {bbox['height']}px")
    
    # Рекурсивно обрабатываем детей
    if 'children' in node and isinstance(node['children'], list):
        for child in node['children']:
            _extract_styles_recursive(child, result)
    
    return result

@mcp.tool
async def extract_styles_from_layout(figma_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Анализирует JSON-структуру макета Figma и извлекает все уникальные стили.
    
    Args:
        figma_data (Dict[str, Any]): JSON-ответ от Figma API.
    
    Returns:
        Dict[str, Any]: Структурированные стили.
    """
    if not figma_data or 'document' not in figma_data:
        raise ValueError("Некорректные данные Figma")
    
    raw_styles = _extract_styles_recursive(figma_data.get('document', {}))
    
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
    
    TOOL_CALLS_TOTAL.labels(tool_name="extract_styles_from_layout", status="success").inc()
    return styles

@mcp.tool
async def export_styles_to_css(
    figma_data: Dict[str, Any],
    css_format: str = "css_variables"
) -> Dict[str, Any]:
    """
    Экспортирует извлеченные стили в CSS.
    
    Args:
        figma_data (Dict[str, Any]): JSON-ответ от Figma API.
        css_format (str): Формат вывода CSS.
    
    Returns:
        Dict[str, Any]: CSS-код и метаданные.
    """
    styles_data = await extract_styles_from_layout(figma_data)
    
    css_lines = []
    if css_format == "css_variables":
        css_lines.append(":root {")
        for i, color in enumerate(styles_data.get('colors', [])):
            css_lines.append(f"  --color-{i + 1}: {color};")
        css_lines.append("}")
    
    return {
        "css": "\n".join(css_lines),
        "metadata": styles_data['summary']
    }