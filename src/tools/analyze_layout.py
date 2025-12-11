"""Инструмент для анализа макета Figma и извлечения его структуры."""
from typing import Dict, Any, List, Optional
import os
import time
from mcp_instance import mcp
from metrics import (
    logger, TOOL_CALLS_TOTAL, TOOL_DURATION_SECONDS,
    FIGMA_API_CALLS_TOTAL
)
from figma_api import figma_api
from utils import (
    flatten_figma_tree, extract_component_properties,
    calculate_similarity_score, log_operation, timestamp
)
from validators import (
    validate_figma_file_key, validate_node_data,
    validate_response_size, validate_figma_response
)

# ID тестового файла с компонентами по умолчанию
TEST_FILE_ID = os.getenv("TEST_FILE_ID", "d4qp6XOTZc3abUbq5UUDe7")

@mcp.tool
async def analyze_figma_layout(
    file_key: str = TEST_FILE_ID,
    include_components: bool = True,
    include_text_styles: bool = True,
    include_color_styles: bool = True,
    max_depth: int = 5
) -> Dict[str, Any]:
    """
    Анализ макета Figma для извлечения структуры, компонентов и стилей.
    
    Этот инструмент анализирует файл Figma с макетом (например, форму входа, страницу продукта)
    и возвращает структурированную информацию о всех элементах макета, включая компоненты,
    текстовые стили, цвета и иерархию элементов. Информация может быть использована агентом
    для понимания структуры макета перед генерацией кода.
    
    Args:
        file_key (str): Ключ файла Figma с макетом для анализа.
                       По умолчанию используется тестовый файл с компонентами.
        include_components (bool): Включить информацию о компонентах и их экземплярах.
        include_text_styles (bool): Включить анализ текстовых стилей.
        include_color_styles (bool): Включить анализ цветовых стилей.
        max_depth (int): Максимальная глубина рекурсивного анализа дерева.
        
    Returns:
        Dict[str, Any]: Структурированные данные макета:
            - metadata: Метаданные файла и анализа
            - structure: Иерархическая структура макета
            - components: Найденные компоненты и их экземпляры
            - text_styles: Текстовые стили (если include_text_styles=True)
            - color_styles: Цветовые стили (если include_color_styles=True)
            - layout_analysis: Анализ компоновки (сетки, отступы, выравнивание)
            
    Raises:
        ValueError: Если передан некорректный ключ файла.
        ConnectionError: Если не удалось подключиться к Figma API.
        
    Examples:
        >>> analyze_figma_layout("d4qp6XOTZc3abUbq5UUDe7")
        {
            "metadata": {
                "file_name": "Login Form Mockup",
                "file_key": "d4qp6XOTZc3abUbq5UUDe7",
                "analysis_timestamp": "2024-01-15T10:30:00Z",
                "total_elements": 42,
                "components_found": 5
            },
            "structure": [
                {
                    "id": "1:23",
                    "name": "Login Form",
                    "type": "FRAME",
                    "children": [...]
                }
            ],
            "components": [
                {
                    "name": "Button/Primary",
                    "type": "INSTANCE",
                    "props": {"variant": "primary", "size": "medium"},
                    "position": {"x": 100, "y": 200}
                }
            ]
        }
        
    Note:
        - Инструмент анализирует только структуру макета, без генерации кода
        - Для глубоких файлов рекомендуется использовать max_depth=3-5
        - Цветовые и текстовые стили извлекаются из свойств элементов
    """
    
    start_time = time.time()
    tool_name = "analyze_figma_layout"
    
    try:
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="started").inc()
        logger.info(f"Starting layout analysis for file: {file_key}")
        
        # Валидация входных данных
        validate_figma_file_key(file_key)
        
        if not figma_api:
            raise ConnectionError("Figma API не инициализирован. Проверьте токен доступа.")
        
        # Получаем информацию о файле
        file_info = await figma_api.get_file(file_key)
        validate_figma_response(file_info, ["name", "document", "lastModified"])
        
        file_name = file_info.get("name", "Unknown")
        document = file_info.get("document", {})
        
        logger.info(f"Analyzing layout: {file_name} (depth limit: {max_depth})")
        
        # Инициализируем результаты
        results = {
            "metadata": {
                "file_name": file_name,
                "file_key": file_key,
                "file_url": f"https://www.figma.com/file/{file_key}",
                "last_modified": file_info.get("lastModified"),
                "thumbnail_url": file_info.get("thumbnailUrl"),
                "analysis_timestamp": timestamp(),
                "analysis_options": {
                    "include_components": include_components,
                    "include_text_styles": include_text_styles,
                    "include_color_styles": include_color_styles,
                    "max_depth": max_depth
                }
            },
            "structure": {},
            "components": [],
            "text_styles": [],
            "color_styles": [],
            "layout_analysis": {},
            "statistics": {},
            "errors": []
        }
        
        # Анализируем структуру документа
        logger.info("Analyzing document structure...")
        structure_data = await _analyze_document_structure(document, max_depth)
        results["structure"] = structure_data
        
        # Извлекаем компоненты
        if include_components:
            logger.info("Extracting components...")
            components_data = await _extract_components_from_document(document, file_key)
            results["components"] = components_data
        
        # Извлекаем текстовые стили
        if include_text_styles:
            logger.info("Extracting text styles...")
            text_styles_data = _extract_text_styles(document)
            results["text_styles"] = text_styles_data
        
        # Извлекаем цветовые стили
        if include_color_styles:
            logger.info("Extracting color styles...")
            color_styles_data = _extract_color_styles(document)
            results["color_styles"] = color_styles_data
        
        # Анализируем компоновку
        logger.info("Analyzing layout composition...")
        layout_analysis = _analyze_layout_composition(document)
        results["layout_analysis"] = layout_analysis
        
        # Генерируем статистику
        results["statistics"] = _generate_statistics(results)
        
        # Обновляем метаданные
        results["metadata"].update({
            "analysis_duration_seconds": round(time.time() - start_time, 2),
            "errors_count": len(results["errors"])
        })
        
        # Обновляем метрики
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="success").inc()
        TOOL_DURATION_SECONDS.labels(tool_name=tool_name).observe(time.time() - start_time)
        
        logger.info(f"Layout analysis completed: {results['statistics'].get('total_elements', 0)} elements analyzed")
        
        # Валидация размера ответа
        validate_response_size(results)
        
        # Логируем операцию
        log_operation("analyze_figma_layout", {
            "file_key": file_key,
            "components_found": len(results["components"]),
            "duration": round(time.time() - start_time, 2)
        })
        
        return results
        
    except Exception as e:
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="error").inc()
        logger.error(f"Error in analyze_figma_layout: {e}")
        raise
    
    finally:
        duration = time.time() - start_time
        logger.debug(f"Tool {tool_name} executed in {duration:.2f} seconds")


async def _analyze_document_structure(document: Dict[str, Any], max_depth: int) -> Dict[str, Any]:
    """Анализ структуры документа Figma."""
    
    def analyze_node(node: Dict[str, Any], current_depth: int = 0) -> Dict[str, Any]:
        """Рекурсивный анализ ноды."""
        if current_depth > max_depth:
            return {
                "id": node.get("id"),
                "name": node.get("name", "Unnamed"),
                "type": node.get("type"),
                "depth": current_depth,
                "skipped": True,
                "skip_reason": f"Maximum depth {max_depth} reached"
            }
        
        node_info = {
            "id": node.get("id"),
            "name": node.get("name", "Unnamed"),
            "type": node.get("type"),
            "depth": current_depth,
            "visible": node.get("visible", True),
            "locked": node.get("locked", False),
            "bounding_box": node.get("absoluteBoundingBox"),
            "styles": _extract_node_styles(node),
            "constraints": node.get("constraints"),
            "layout_mode": node.get("layoutMode"),
            "primary_axis_align_items": node.get("primaryAxisAlignItems"),
            "counter_axis_align_items": node.get("counterAxisAlignItems"),
            "padding": node.get("padding"),
            "item_spacing": node.get("itemSpacing"),
            "children": []
        }
        
        # Добавляем информацию о тексте для текстовых нод
        if node.get("type") == "TEXT":
            node_info.update({
                "text_content": node.get("characters", ""),
                "text_style": _extract_text_style(node),
                "text_auto_resize": node.get("textAutoResize"),
                "text_align_horizontal": node.get("textAlignHorizontal"),
                "text_align_vertical": node.get("textAlignVertical")
            })
        
        # Добавляем информацию о компонентах
        if node.get("type") in ["COMPONENT", "COMPONENT_SET", "INSTANCE"]:
            node_info.update({
                "component_id": node.get("componentId"),
                "is_main_component": node.get("type") == "COMPONENT",
                "is_component_set": node.get("type") == "COMPONENT_SET",
                "is_instance": node.get("type") == "INSTANCE",
                "component_properties": node.get("componentProperties", {})
            })
        
        # Рекурсивно анализируем детей
        if "children" in node and isinstance(node["children"], list) and current_depth < max_depth:
            for child in node["children"]:
                child_info = analyze_node(child, current_depth + 1)
                node_info["children"].append(child_info)
        
        return node_info
    
    return analyze_node(document)


async def _extract_components_from_document(document: Dict[str, Any], file_key: str) -> List[Dict[str, Any]]:
    """Извлечение компонентов и их экземпляров из документа."""
    components = []
    instances = []
    
    def find_components(node: Dict[str, Any]):
        """Рекурсивный поиск компонентов и экземпляров."""
        node_type = node.get("type")
        
        if node_type == "COMPONENT":
            # Это основной компонент
            component_info = {
                "id": node.get("id"),
                "name": node.get("name", "Unnamed"),
                "key": node.get("key"),  # Ключ компонента (если есть)
                "description": node.get("description", ""),
                "type": "component",
                "is_main": True,
                "bounding_box": node.get("absoluteBoundingBox"),
                "props": extract_component_properties(node),
                "figma_url": f"https://www.figma.com/file/{file_key}/?node-id={node.get('id')}"
            }
            components.append(component_info)
        
        elif node_type == "INSTANCE":
            # Это экземпляр компонента
            component_id = node.get("componentId")
            if component_id:
                instance_info = {
                    "id": node.get("id"),
                    "name": node.get("name", "Unnamed"),
                    "type": "instance",
                    "component_id": component_id,
                    "component_properties": node.get("componentProperties", {}),
                    "bounding_box": node.get("absoluteBoundingBox"),
                    "position": {
                        "x": node.get("absoluteBoundingBox", {}).get("x", 0),
                        "y": node.get("absoluteBoundingBox", {}).get("y", 0)
                    },
                    "overrides": _extract_instance_overrides(node)
                }
                instances.append(instance_info)
        
        # Рекурсивно ищем в детях
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                find_components(child)
    
    # Запускаем поиск
    find_components(document)
    
    # Связываем экземпляры с их компонентами
    for instance in instances:
        component_id = instance["component_id"]
        # Ищем соответствующий компонент
        matching_component = next(
            (c for c in components if c["id"] == component_id),
            None
        )
        
        if matching_component:
            instance["component_name"] = matching_component["name"]
            instance["component_info"] = {
                "name": matching_component["name"],
                "props": matching_component.get("props", [])
            }
    
    # Объединяем компоненты и экземпляры
    all_components = components + instances
    
    # Группируем по типам для статистики
    component_types = {}
    for comp in all_components:
        comp_type = comp.get("type", "unknown")
        component_types[comp_type] = component_types.get(comp_type, 0) + 1
    
    logger.info(f"Found {len(components)} components and {len(instances)} instances")
    logger.info(f"Component types: {component_types}")
    
    return all_components


def _extract_instance_overrides(instance_node: Dict[str, Any]) -> Dict[str, Any]:
    """Извлечение переопределений в экземпляре компонента."""
    overrides = {
        "text_overrides": [],
        "color_overrides": [],
        "visibility_overrides": [],
        "property_overrides": {}
    }
    
    # Проверяем, есть ли переопределенные свойства
    if "componentProperties" in instance_node:
        for prop_name, prop_value in instance_node["componentProperties"].items():
            overrides["property_overrides"][prop_name] = prop_value
    
    # Рекурсивно ищем переопределения в детях
    def find_overrides(node: Dict[str, Any], path: str = ""):
        current_path = f"{path}/{node.get('name', '')}" if path else node.get('name', '')
        
        # Проверяем переопределения текста
        if "overrides" in node and "characters" in node.get("overrides", {}):
            overrides["text_overrides"].append({
                "path": current_path,
                "original": node.get("characters", ""),
                "override": node["overrides"]["characters"]
            })
        
        # Проверяем переопределения цвета
        if "fills" in node and isinstance(node["fills"], list):
            for i, fill in enumerate(node["fills"]):
                if "overrides" in node and f"fills[{i}]" in node.get("overrides", {}):
                    overrides["color_overrides"].append({
                        "path": current_path,
                        "fill_index": i,
                        "override": node["overrides"][f"fills[{i}]"]
                    })
        
        # Проверяем видимость
        if "visible" in node and "overrides" in node and "visible" in node["overrides"]:
            overrides["visibility_overrides"].append({
                "path": current_path,
                "original": node.get("visible", True),
                "override": node["overrides"]["visible"]
            })
        
        # Рекурсивно проверяем детей
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                find_overrides(child, current_path)
    
    find_overrides(instance_node)
    
    return overrides


def _extract_text_styles(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Извлечение текстовых стилей из документа."""
    text_styles = []
    seen_styles = set()
    
    def extract_from_node(node: Dict[str, Any]):
        if node.get("type") == "TEXT":
            style_info = _extract_text_style(node)
            
            # Создаем уникальный ключ для стиля
            style_key = (
                f"{style_info.get('font_family')}_{style_info.get('font_weight')}_"
                f"{style_info.get('font_size')}_{style_info.get('line_height')}"
            )
            
            if style_key not in seen_styles:
                text_styles.append({
                    **style_info,
                    "node_id": node.get("id"),
                    "node_name": node.get("name", ""),
                    "text_content": node.get("characters", "")[:100]  # Первые 100 символов
                })
                seen_styles.add(style_key)
        
        # Рекурсивно обрабатываем детей
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                extract_from_node(child)
    
    extract_from_node(document)
    
    # Группируем стили по категориям
    categorized_styles = {}
    for style in text_styles:
        font_size = style.get("font_size", 0)
        
        # Определяем категорию по размеру шрифта
        if font_size >= 24:
            category = "heading"
        elif font_size >= 16:
            category = "subheading"
        elif font_size >= 14:
            category = "body_large"
        elif font_size >= 12:
            category = "body"
        else:
            category = "caption"
        
        if category not in categorized_styles:
            categorized_styles[category] = []
        
        categorized_styles[category].append(style)
    
    # Преобразуем обратно в список с категориями
    result = []
    for category, styles in categorized_styles.items():
        result.append({
            "category": category,
            "styles": styles,
            "count": len(styles)
        })
    
    logger.info(f"Extracted {len(text_styles)} unique text styles in {len(categorized_styles)} categories")
    
    return result


def _extract_text_style(node: Dict[str, Any]) -> Dict[str, Any]:
    """Извлечение информации о текстовом стиле из ноды."""
    style_info = {
        "font_family": "Unknown",
        "font_weight": "Normal",
        "font_size": 14,
        "line_height": "normal",
        "letter_spacing": 0,
        "text_align": "LEFT",
        "text_case": "ORIGINAL",
        "text_decoration": "NONE",
        "color": "#000000"
    }
    
    # Извлекаем информацию о шрифте
    if "style" in node:
        style = node["style"]
        
        if "fontFamily" in style:
            style_info["font_family"] = style["fontFamily"]
        
        if "fontWeight" in style:
            style_info["font_weight"] = style["fontWeight"]
        
        if "fontSize" in style:
            style_info["font_size"] = style["fontSize"]
        
        if "lineHeightPx" in style:
            style_info["line_height"] = f"{style['lineHeightPx']}px"
        elif "lineHeightPercent" in style:
            style_info["line_height"] = f"{style['lineHeightPercent']}%"
        
        if "letterSpacing" in style:
            style_info["letter_spacing"] = style["letterSpacing"]
        
        if "textAlignHorizontal" in style:
            style_info["text_align"] = style["textAlignHorizontal"]
        
        if "textCase" in style:
            style_info["text_case"] = style["textCase"]
        
        if "textDecoration" in style:
            style_info["text_decoration"] = style["textDecoration"]
    
    # Извлекаем цвет текста
    if "fills" in node and isinstance(node["fills"], list):
        for fill in node["fills"]:
            if fill.get("type") == "SOLID" and "color" in fill:
                color = fill["color"]
                style_info["color"] = _format_color(color)
                break
    
    return style_info


def _extract_color_styles(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Извлечение цветовых стилей из документа."""
    color_styles = []
    seen_colors = set()
    
    def extract_from_node(node: Dict[str, Any]):
        # Извлекаем цвета из fills
        if "fills" in node and isinstance(node["fills"], list):
            for fill in node["fills"]:
                if fill.get("type") == "SOLID" and "color" in fill:
                    color = fill["color"]
                    color_value = _format_color(color)
                    
                    if color_value not in seen_colors:
                        color_styles.append({
                            "color": color_value,
                            "rgb": color,
                            "opacity": color.get("a", 1),
                            "node_id": node.get("id"),
                            "node_name": node.get("name", ""),
                            "node_type": node.get("type"),
                            "usage": "fill"
                        })
                        seen_colors.add(color_value)
        
        # Извлекаем цвета из strokes
        if "strokes" in node and isinstance(node["strokes"], list):
            for stroke in node["strokes"]:
                if stroke.get("type") == "SOLID" and "color" in stroke:
                    color = stroke["color"]
                    color_value = _format_color(color)
                    
                    if color_value not in seen_colors:
                        color_styles.append({
                            "color": color_value,
                            "rgb": color,
                            "opacity": color.get("a", 1),
                            "node_id": node.get("id"),
                            "node_name": node.get("name", ""),
                            "node_type": node.get("type"),
                            "usage": "stroke"
                        })
                        seen_colors.add(color_value)
        
        # Извлекаем цвета из эффектов (тени)
        if "effects" in node and isinstance(node["effects"], list):
            for effect in node["effects"]:
                if effect.get("type") == "DROP_SHADOW" and "color" in effect:
                    color = effect["color"]
                    color_value = _format_color(color)
                    
                    if color_value not in seen_colors:
                        color_styles.append({
                            "color": color_value,
                            "rgb": color,
                            "opacity": color.get("a", 1),
                            "node_id": node.get("id"),
                            "node_name": node.get("name", ""),
                            "node_type": node.get("type"),
                            "usage": "shadow",
                            "shadow_info": {
                                "offset_x": effect.get("offset", {}).get("x", 0),
                                "offset_y": effect.get("offset", {}).get("y", 0),
                                "radius": effect.get("radius", 0),
                                "spread": effect.get("spread", 0)
                            }
                        })
                        seen_colors.add(color_value)
        
        # Рекурсивно обрабатываем детей
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                extract_from_node(child)
    
    extract_from_node(document)
    
    # Группируем цвета по категориям
    categorized_colors = {}
    for color_style in color_styles:
        color_value = color_style["color"]
        
        # Определяем категорию по использованию и тону
        usage = color_style.get("usage", "unknown")
        rgb = color_style.get("rgb", {})
        
        # Простая классификация по яркости
        brightness = (rgb.get("r", 0) + rgb.get("g", 0) + rgb.get("b", 0)) / 3
        if brightness > 0.7:
            tone = "light"
        elif brightness < 0.3:
            tone = "dark"
        else:
            tone = "medium"
        
        category = f"{usage}_{tone}"
        
        if category not in categorized_colors:
            categorized_colors[category] = []
        
        categorized_colors[category].append(color_style)
    
    # Преобразуем обратно в список с категориями
    result = []
    for category, colors in categorized_colors.items():
        result.append({
            "category": category,
            "colors": colors,
            "count": len(colors)
        })
    
    logger.info(f"Extracted {len(color_styles)} unique colors in {len(categorized_colors)} categories")
    
    return result


def _format_color(color: Dict[str, float]) -> str:
    """Форматирование цвета в строку."""
    r = int(color.get("r", 0) * 255)
    g = int(color.get("g", 0) * 255)
    b = int(color.get("b", 0) * 255)
    a = color.get("a", 1)
    
    if a == 1:
        return f"rgb({r}, {g}, {b})"
    else:
        return f"rgba({r}, {g}, {b}, {a})"


def _extract_node_styles(node: Dict[str, Any]) -> Dict[str, Any]:
    """Извлечение стилей из ноды."""
    styles = {
        "fills": [],
        "strokes": [],
        "effects": [],
        "opacity": node.get("opacity", 1),
        "blend_mode": node.get("blendMode", "PASS_THROUGH")
    }
    
    # Извлекаем fills
    if "fills" in node and isinstance(node["fills"], list):
        for fill in node["fills"]:
            fill_info = {
                "type": fill.get("type"),
                "visible": fill.get("visible", True),
                "opacity": fill.get("opacity", 1),
                "blend_mode": fill.get("blendMode", "NORMAL")
            }
            
            if fill.get("type") == "SOLID" and "color" in fill:
                fill_info["color"] = _format_color(fill["color"])
            
            styles["fills"].append(fill_info)
    
    # Извлекаем strokes
    if "strokes" in node and isinstance(node["strokes"], list):
        for stroke in node["strokes"]:
            stroke_info = {
                "type": stroke.get("type"),
                "visible": stroke.get("visible", True),
                "opacity": stroke.get("opacity", 1),
                "blend_mode": stroke.get("blendMode", "NORMAL"),
                "stroke_weight": node.get("strokeWeight", 1),
                "stroke_align": node.get("strokeAlign", "INSIDE")
            }
            
            if stroke.get("type") == "SOLID" and "color" in stroke:
                stroke_info["color"] = _format_color(stroke["color"])
            
            styles["strokes"].append(stroke_info)
    
    # Извлекаем effects
    if "effects" in node and isinstance(node["effects"], list):
        for effect in node["effects"]:
            effect_info = {
                "type": effect.get("type"),
                "visible": effect.get("visible", True),
                "radius": effect.get("radius", 0)
            }
            
            if effect.get("type") == "DROP_SHADOW" and "color" in effect:
                effect_info["color"] = _format_color(effect["color"])
                effect_info["offset"] = effect.get("offset", {})
                effect_info["spread"] = effect.get("spread", 0)
            
            styles["effects"].append(effect_info)
    
    return styles


def _analyze_layout_composition(document: Dict[str, Any]) -> Dict[str, Any]:
    """Анализ компоновки макета."""
    analysis = {
        "grids": [],
        "spacing_patterns": [],
        "alignment_patterns": [],
        "responsive_patterns": [],
        "layout_metrics": {}
    }
    
    grid_data = []
    spacing_data = []
    alignment_data = []
    
    def analyze_node_layout(node: Dict[str, Any], parent_info: Dict[str, Any] = None):
        """Анализ компоновки ноды."""
        
        # Проверяем использование сеток
        if node.get("layoutGrids") and isinstance(node["layoutGrids"], list):
            for grid in node["layoutGrids"]:
                grid_info = {
                    "node_id": node.get("id"),
                    "node_name": node.get("name", ""),
                    "pattern": grid.get("pattern"),
                    "section_size": grid.get("sectionSize"),
                    "gutter_size": grid.get("gutterSize"),
                    "alignment": grid.get("alignment"),
                    "count": grid.get("count"),
                    "offset": grid.get("offset")
                }
                grid_data.append(grid_info)
        
        # Проверяем, является ли нода контейнером с детьми
        if "children" in node and isinstance(node["children"], list) and len(node["children"]) > 0:
            children = node["children"]
            
            # Анализируем отступы между детьми
            if len(children) > 1:
                spacing_pattern = _analyze_spacing_pattern(children)
                if spacing_pattern:
                    spacing_data.append({
                        "node_id": node.get("id"),
                        "node_name": node.get("name", ""),
                        "pattern": spacing_pattern,
                        "children_count": len(children)
                    })
            
            # Анализируем выравнивание детей
            alignment_pattern = _analyze_alignment_pattern(children)
            if alignment_pattern:
                alignment_data.append({
                    "node_id": node.get("id"),
                    "node_name": node.get("name", ""),
                    "pattern": alignment_pattern,
                    "children_count": len(children)
                })
            
            # Проверяем responsive паттерны
            responsive_pattern = _analyze_responsive_pattern(node, children)
            if responsive_pattern:
                analysis["responsive_patterns"].append({
                    "node_id": node.get("id"),
                    "node_name": node.get("name", ""),
                    "pattern": responsive_pattern
                })
        
        # Рекурсивно анализируем детей
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                analyze_node_layout(child, {
                    "id": node.get("id"),
                    "name": node.get("name", ""),
                    "type": node.get("type")
                })
    
    # Запускаем анализ
    analyze_node_layout(document)
    
    # Агрегируем результаты
    if grid_data:
        analysis["grids"] = grid_data
    
    if spacing_data:
        analysis["spacing_patterns"] = spacing_data
    
    if alignment_data:
        analysis["alignment_patterns"] = alignment_data
    
    # Рассчитываем метрики компоновки
    analysis["layout_metrics"] = _calculate_layout_metrics(document)
    
    return analysis


def _analyze_spacing_pattern(children: List[Dict[str, Any]]) -> Optional[str]:
    """Анализ паттерна отступов между элементами."""
    if len(children) < 2:
        return None
    
    # Извлекаем позиции и размеры детей
    positions = []
    for child in children:
        bbox = child.get("absoluteBoundingBox", {})
        if bbox:
            positions.append({
                "x": bbox.get("x", 0),
                "y": bbox.get("y", 0),
                "width": bbox.get("width", 0),
                "height": bbox.get("height", 0)
            })
    
    if len(positions) < 2:
        return None
    
    # Проверяем горизонтальное расположение
    x_positions = [p["x"] for p in positions]
    x_positions.sort()
    
    # Проверяем равные отступы по X
    if len(x_positions) > 1:
        diffs = [x_positions[i+1] - x_positions[i] for i in range(len(x_positions)-1)]
        if all(abs(d - diffs[0]) < 1 for d in diffs):  # Допуск 1px
            return f"horizontal_equal_spacing_{diffs[0]:.0f}px"
    
    # Проверяем вертикальное расположение
    y_positions = [p["y"] for p in positions]
    y_positions.sort()
    
    # Проверяем равные отступы по Y
    if len(y_positions) > 1:
        diffs = [y_positions[i+1] - y_positions[i] for i in range(len(y_positions)-1)]
        if all(abs(d - diffs[0]) < 1 for d in diffs):  # Допуск 1px
            return f"vertical_equal_spacing_{diffs[0]:.0f}px"
    
    return "irregular_spacing"


def _analyze_alignment_pattern(children: List[Dict[str, Any]]) -> Optional[str]:
    """Анализ паттерна выравнивания элементов."""
    if len(children) < 2:
        return None
    
    # Извлекаем позиции и размеры детей
    positions = []
    for child in children:
        bbox = child.get("absoluteBoundingBox", {})
        if bbox:
            positions.append({
                "x": bbox.get("x", 0),
                "y": bbox.get("y", 0),
                "width": bbox.get("width", 0),
                "height": bbox.get("height", 0),
                "center_x": bbox.get("x", 0) + bbox.get("width", 0) / 2,
                "center_y": bbox.get("y", 0) + bbox.get("height", 0) / 2
            })
    
    if len(positions) < 2:
        return None
    
    # Проверяем выравнивание по левому краю
    left_edges = [p["x"] for p in positions]
    if max(left_edges) - min(left_edges) < 2:  # Допуск 2px
        return "left_aligned"
    
    # Проверяем выравнивание по правому краю
    right_edges = [p["x"] + p["width"] for p in positions]
    if max(right_edges) - min(right_edges) < 2:  # Допуск 2px
        return "right_aligned"
    
    # Проверяем выравнивание по верхнему краю
    top_edges = [p["y"] for p in positions]
    if max(top_edges) - min(top_edges) < 2:  # Допуск 2px
        return "top_aligned"
    
    # Проверяем выравнивание по нижнему краю
    bottom_edges = [p["y"] + p["height"] for p in positions]
    if max(bottom_edges) - min(bottom_edges) < 2:  # Допуск 2px
        return "bottom_aligned"
    
    # Проверяем выравнивание по центру по X
    center_xs = [p["center_x"] for p in positions]
    if max(center_xs) - min(center_xs) < 2:  # Допуск 2px
        return "center_x_aligned"
    
    # Проверяем выравнивание по центру по Y
    center_ys = [p["center_y"] for p in positions]
    if max(center_ys) - min(center_ys) < 2:  # Допуск 2px
        return "center_y_aligned"
    
    return None


def _analyze_responsive_pattern(node: Dict[str, Any], children: List[Dict[str, Any]]) -> Optional[str]:
    """Анализ responsive паттернов."""
    
    # Проверяем, является ли нода фреймом с auto-layout
    if node.get("layoutMode") in ["HORIZONTAL", "VERTICAL"]:
        layout_mode = node["layoutMode"]
        
        # Проверяем, есть ли responsive поведение
        counter_axis_sizing = node.get("counterAxisSizingMode", "FIXED")
        primary_axis_sizing = node.get("primaryAxisSizingMode", "FIXED")
        
        if counter_axis_sizing == "AUTO" or primary_axis_sizing == "AUTO":
            pattern = f"{layout_mode.lower()}_auto_layout"
            
            if node.get("layoutWrap") == "WRAP":
                pattern += "_wrap"
            
            return pattern
    
    # Проверяем constraints детей для responsive поведения
    responsive_children = 0
    for child in children:
        constraints = child.get("constraints")
        if constraints:
            horizontal = constraints.get("horizontal")
            vertical = constraints.get("vertical")
            
            # Проверяем, есть ли responsive constraints
            if horizontal in ["LEFT_RIGHT", "CENTER", "SCALE"]:
                responsive_children += 1
            if vertical in ["TOP_BOTTOM", "CENTER", "SCALE"]:
                responsive_children += 1
    
    if responsive_children > len(children) * 0.5:  # Более 50% детей responsive
        return "responsive_constraints"
    
    return None


def _calculate_layout_metrics(document: Dict[str, Any]) -> Dict[str, Any]:
    """Расчет метрик компоновки."""
    metrics = {
        "total_nodes": 0,
        "depth_stats": {},
        "type_distribution": {},
        "container_stats": {},
        "text_density": 0,
        "component_density": 0
    }
    
    text_nodes = 0
    component_nodes = 0
    container_nodes = 0
    max_depth = 0
    
    def traverse_for_metrics(node: Dict[str, Any], depth: int = 0):
        nonlocal text_nodes, component_nodes, container_nodes, max_depth
        
        metrics["total_nodes"] += 1
        max_depth = max(max_depth, depth)
        
        # Обновляем распределение по глубине
        depth_key = f"depth_{depth}"
        metrics["depth_stats"][depth_key] = metrics["depth_stats"].get(depth_key, 0) + 1
        
        # Обновляем распределение по типам
        node_type = node.get("type", "UNKNOWN")
        metrics["type_distribution"][node_type] = metrics["type_distribution"].get(node_type, 0) + 1
        
        # Считаем текстовые ноды
        if node_type == "TEXT":
            text_nodes += 1
        
        # Считаем компоненты
        if node_type in ["COMPONENT", "INSTANCE", "COMPONENT_SET"]:
            component_nodes += 1
        
        # Считаем контейнеры
        if node_type in ["FRAME", "GROUP", "SECTION"]:
            container_nodes += 1
        
        # Считаем детей
        child_count = len(node.get("children", []))
        if child_count > 0:
            container_stats = metrics["container_stats"]
            container_stats["total_containers"] = container_stats.get("total_containers", 0) + 1
            container_stats["total_children"] = container_stats.get("total_children", 0) + child_count
            
            # Обновляем статистику по количеству детей
            child_count_key = f"children_{child_count}"
            container_stats[child_count_key] = container_stats.get(child_count_key, 0) + 1
        
        # Рекурсивно обрабатываем детей
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                traverse_for_metrics(child, depth + 1)
    
    traverse_for_metrics(document)
    
    # Рассчитываем плотности
    if metrics["total_nodes"] > 0:
        metrics["text_density"] = round(text_nodes / metrics["total_nodes"], 3)
        metrics["component_density"] = round(component_nodes / metrics["total_nodes"], 3)
    
    # Рассчитываем среднее количество детей у контейнеров
    if container_nodes > 0:
        total_children = metrics["container_stats"].get("total_children", 0)
        metrics["container_stats"]["avg_children_per_container"] = round(total_children / container_nodes, 2)
    
    metrics["max_depth"] = max_depth
    
    return metrics


def _generate_statistics(results: Dict[str, Any]) -> Dict[str, Any]:
    """Генерация статистики по анализу."""
    stats = {
        "total_elements": 0,
        "components_found": len(results.get("components", [])),
        "text_styles_found": sum(cat.get("count", 0) for cat in results.get("text_styles", [])),
        "color_styles_found": sum(cat.get("count", 0) for cat in results.get("color_styles", [])),
        "grids_found": len(results.get("layout_analysis", {}).get("grids", [])),
        "spacing_patterns": len(results.get("layout_analysis", {}).get("spacing_patterns", [])),
        "alignment_patterns": len(results.get("layout_analysis", {}).get("alignment_patterns", [])),
        "responsive_patterns": len(results.get("layout_analysis", {}).get("responsive_patterns", [])),
        "component_types": {},
        "text_style_categories": {},
        "color_style_categories": {}
    }
    
    # Считаем общее количество элементов
    def count_elements(structure: Dict[str, Any]) -> int:
        count = 1  # Текущий элемент
        for child in structure.get("children", []):
            count += count_elements(child)
        return count
    
    if "structure" in results and results["structure"]:
        stats["total_elements"] = count_elements(results["structure"])
    
    # Анализируем типы компонентов
    for component in results.get("components", []):
        comp_type = component.get("type", "unknown")
        stats["component_types"][comp_type] = stats["component_types"].get(comp_type, 0) + 1
    
    # Анализируем категории текстовых стилей
    for category in results.get("text_styles", []):
        cat_name = category.get("category", "unknown")
        stats["text_style_categories"][cat_name] = category.get("count", 0)
    
    # Анализируем категории цветовых стилей
    for category in results.get("color_styles", []):
        cat_name = category.get("category", "unknown")
        stats["color_style_categories"][cat_name] = category.get("count", 0)
    
    # Рассчитываем плотность компонентов
    if stats["total_elements"] > 0:
        stats["component_density_percent"] = round((stats["components_found"] / stats["total_elements"]) * 100, 1)
    
    return stats