"""Инструмент для получения компонентов дизайн-системы из Figma через Tokens Studio."""
from typing import Dict, Any, List, Optional
import os
from mcp_instance import mcp
from metrics import (
    logger, TOOL_CALLS_TOTAL, TOOL_DURATION_SECONDS, 
    COMPONENTS_SCANNED, FIGMA_API_CALLS_TOTAL
)
from figma_api import init_figma_api, figma_api
from tokens_parser import TokensStudioParser
from validators import (
    validate_figma_file_key, validate_component_limit, 
    validate_response_size, validate_figma_response
)
import time

# Инициализация Figma API при загрузке модуля
FIGMA_ACCESS_TOKEN = os.getenv("FIGMA_ACCESS_TOKEN", "figd_LQnLwvow3ffJ9FLOsiG6bUDvLQ1xq2xcR-BZ3ANr")
KONTUR_UI_FILE_ID = os.getenv("KONTUR_UI_FILE_ID", "KQc2jUV5CuCDqZ7hHTX0vc")

# Инициализируем Figma API
try:
    figma_client = init_figma_api(FIGMA_ACCESS_TOKEN)
    logger.info("Figma API initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Figma API: {e}")
    figma_client = None

@mcp.tool
async def get_design_system_components(
    file_key: str = KONTUR_UI_FILE_ID,
    include_tokens: bool = True,
    include_styles: bool = True,
    include_variants: bool = True
) -> Dict[str, Any]:
    """
    Получение всех компонентов, токенов и стилей из дизайн-системы Kontur UI через Figma API и Tokens Studio.
    
    Этот инструмент сканирует файл Figma с дизайн-системой Kontur UI и возвращает структурированные данные
    о компонентах, их пропсах, вариантах и связанных токенах. Данные могут быть использованы агентом
    для понимания доступных компонентов и их свойств при генерации кода.
    
    Args:
        file_key (str): Ключ файла Figma с дизайн-системой Kontur UI.
                       По умолчанию используется стандартный файл Kontur UI.
        include_tokens (bool): Включить токены дизайн-системы (цвета, шрифты, отступы).
        include_styles (bool): Включить стили Figma.
        include_variants (bool): Включить варианты компонентов (разные состояния и размеры).
        
    Returns:
        Dict[str, Any]: Структурированные данные дизайн-системы:
            - metadata: Метаданные файла и сканирования
            - components: Список компонентов с их свойствами
            - tokens: Токены дизайн-системы (если include_tokens=True)
            - styles: Стили Figma (если include_styles=True)
            - component_sets: Группы компонентов (component sets)
            
    Raises:
        ValueError: Если передан некорректный ключ файла или произошла ошибка API.
        ConnectionError: Если не удалось подключиться к Figma API.
        
    Examples:
        >>> get_design_system_components()
        {
            "metadata": {
                "file_name": "Kontur UI Library",
                "file_key": "KQc2jUV5CuCDqZ7hHTX0vc",
                "scan_timestamp": "2024-01-15T10:30:00Z",
                "components_count": 145,
                "tokens_count": 256
            },
            "components": [
                {
                    "name": "Button",
                    "type": "component_set",
                    "props": [
                        {"name": "variant", "type": "VARIANT", "values": ["primary", "secondary", "danger"]},
                        {"name": "size", "type": "VARIANT", "values": ["small", "medium", "large"]},
                        {"name": "disabled", "type": "BOOLEAN", "default_value": false}
                    ],
                    "variants": [
                        {"name": "primary", "tokens": {"background": "colors.primary"}},
                        {"name": "secondary", "tokens": {"background": "colors.secondary"}}
                    ],
                    "import_path": "@skbkontur/react-ui/Button"
                }
            ]
        }
        
    Note:
        - Для работы требуется корректный токен Figma API (FIGMA_ACCESS_TOKEN)
        - Инструмент использует данные из Tokens Studio для получения структурированных токенов
        - Компоненты возвращаются с информацией, достаточной для генерации TypeScript типов
    """
    
    start_time = time.time()
    tool_name = "get_design_system_components"
    
    try:
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="started").inc()
        logger.info(f"Starting design system scan for file: {file_key}")
        
        # Валидация входных данных
        validate_figma_file_key(file_key)
        
        if not figma_client:
            raise ConnectionError("Figma API не инициализирован. Проверьте токен доступа.")
        
        # Получаем информацию о файле
        file_info = await figma_client.get_file(file_key)
        validate_figma_response(file_info, ["name", "lastModified"])
        
        file_name = file_info.get("name", "Unknown")
        logger.info(f"Scanning file: {file_name}")
        
        results = {
            "metadata": {
                "file_name": file_name,
                "file_key": file_key,
                "file_url": f"https://www.figma.com/file/{file_key}",
                "last_modified": file_info.get("lastModified"),
                "thumbnail_url": file_info.get("thumbnailUrl"),
                "scan_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "include_tokens": include_tokens,
                "include_styles": include_styles,
                "include_variants": include_variants
            },
            "components": [],
            "tokens": [],
            "styles": [],
            "component_sets": [],
            "errors": []
        }
        
        # Получаем компоненты
        logger.info("Fetching components from Figma...")
        components_data = await figma_client.get_components(file_key)
        validate_figma_response(components_data, ["meta", "components"])
        
        components_list = components_data.get("components", [])
        validate_component_limit(len(components_list))
        
        # Получаем component sets
        component_sets_data = await figma_client.get_component_sets(file_key)
        if "component_sets" in component_sets_data:
            results["component_sets"] = component_sets_data["component_sets"]
        
        # Обрабатываем каждый компонент
        logger.info(f"Processing {len(components_list)} components...")
        
        for component in components_list:
            try:
                component_info = await _process_component(component, file_key, include_variants)
                if component_info:
                    results["components"].append(component_info)
            except Exception as e:
                error_msg = f"Error processing component {component.get('name', 'unknown')}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        # Получаем токены через анализ структуры файла
        if include_tokens:
            logger.info("Extracting tokens from file structure...")
            try:
                tokens_data = await _extract_tokens_from_file(file_key)
                if tokens_data:
                    results["tokens"] = tokens_data
            except Exception as e:
                error_msg = f"Error extracting tokens: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        # Получаем стили Figma
        if include_styles:
            logger.info("Fetching styles from Figma...")
            try:
                styles_data = await figma_client.get_styles(file_key)
                if "styles" in styles_data:
                    results["styles"] = styles_data["styles"]
            except Exception as e:
                error_msg = f"Error fetching styles: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        # Обновляем метаданные с итогами
        results["metadata"].update({
            "components_count": len(results["components"]),
            "component_sets_count": len(results["component_sets"]),
            "tokens_count": len(results["tokens"]),
            "styles_count": len(results["styles"]),
            "errors_count": len(results["errors"]),
            "scan_duration_seconds": round(time.time() - start_time, 2)
        })
        
        # Обновляем метрики
        COMPONENTS_SCANNED.set(len(results["components"]))
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="success").inc()
        TOOL_DURATION_SECONDS.labels(tool_name=tool_name).observe(time.time() - start_time)
        
        logger.info(f"Design system scan completed: {len(results['components'])} components found")
        
        # Валидация размера ответа
        validate_response_size(results)
        
        return results
        
    except Exception as e:
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="error").inc()
        logger.error(f"Error in get_design_system_components: {e}")
        raise
    
    finally:
        duration = time.time() - start_time
        logger.debug(f"Tool {tool_name} executed in {duration:.2f} seconds")


async def _process_component(
    component: Dict[str, Any], 
    file_key: str,
    include_variants: bool
) -> Optional[Dict[str, Any]]:
    """Обработка отдельного компонента."""
    
    component_info = {
        "id": component.get("key"),
        "name": component.get("name", "Unnamed"),
        "description": component.get("description", ""),
        "type": "component",
        "documentation_links": component.get("documentationLinks", []),
        "created_at": component.get("createdAt"),
        "updated_at": component.get("updatedAt"),
        "props": [],
        "variants": [],
        "tokens": [],
        "import_path": _generate_import_path(component.get("name", "")),
        "figma_url": f"https://www.figma.com/file/{file_key}/?node-id={component.get('key')}"
    }
    
    # Получаем детальную информацию о компоненте
    try:
        nodes_data = await figma_api.get_file_nodes(file_key, [component["key"]])
        
        if "nodes" in nodes_data and component["key"] in nodes_data["nodes"]:
            node_info = nodes_data["nodes"][component["key"]]["document"]
            
            # Извлекаем свойства компонента
            component_props = node_info.get("componentPropertyDefinitions", {})
            if component_props:
                component_info["props"] = _extract_component_props(component_props)
            
            # Извлекаем варианты, если это component set
            if node_info.get("type") == "COMPONENT_SET" and include_variants:
                component_info["type"] = "component_set"
                component_info["variants"] = _extract_variants(node_info)
            
            # Извлекаем токены, связанные с компонентом
            component_info["tokens"] = _extract_component_tokens(node_info)
            
            # Извлекаем дополнительные метаданные
            component_info.update({
                "width": node_info.get("absoluteBoundingBox", {}).get("width"),
                "height": node_info.get("absoluteBoundingBox", {}).get("height"),
                "contains_text": _has_text_nodes(node_info),
                "contains_images": _has_image_nodes(node_info),
                "layer_count": _count_layers(node_info)
            })
    
    except Exception as e:
        logger.warning(f"Could not get detailed info for component {component_info['name']}: {e}")
    
    return component_info


def _extract_component_props(component_props: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Извлечение свойств компонента из componentPropertyDefinitions."""
    props_list = []
    
    for prop_name, prop_info in component_props.items():
        prop_data = {
            "name": prop_name,
            "type": prop_info.get("type", "VARIANT"),
            "default_value": prop_info.get("defaultValue"),
            "description": prop_info.get("description", "")
        }
        
        # Добавляем варианты для типа VARIANT
        if prop_info.get("type") == "VARIANT" and "variantOptions" in prop_info:
            prop_data["variant_options"] = prop_info["variantOptions"]
        
        props_list.append(prop_data)
    
    return props_list


def _extract_variants(node_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Извлечение вариантов компонента."""
    variants = []
    
    if "children" in node_info and isinstance(node_info["children"], list):
        for child in node_info["children"]:
            if child.get("type") == "COMPONENT":
                variant_info = {
                    "name": child.get("name", "Unnamed"),
                    "id": child.get("id"),
                    "description": child.get("description", ""),
                    "props": _extract_variant_props(child),
                    "tokens": _extract_component_tokens(child)
                }
                variants.append(variant_info)
    
    return variants


def _extract_variant_props(variant_node: Dict[str, Any]) -> Dict[str, Any]:
    """Извлечение свойств варианта компонента."""
    props = {}
    
    # Проверяем, является ли этот вариант частью component set
    if "componentProperties" in variant_node:
        for prop_name, prop_value in variant_node["componentProperties"].items():
            props[prop_name] = prop_value
    
    return props


def _extract_component_tokens(node_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Извлечение токенов, связанных с компонентом."""
    tokens = []
    
    # Рекурсивно ищем заполнения (fills) и другие стили
    def extract_from_node(node: Dict[str, Any]):
        # Извлекаем fills (заполнения)
        if "fills" in node and isinstance(node["fills"], list):
            for fill in node["fills"]:
                if fill.get("type") == "SOLID" and "color" in fill:
                    color = fill["color"]
                    token = {
                        "type": "color",
                        "name": "fill_color",
                        "value": f"rgba({int(color['r']*255)}, {int(color['g']*255)}, {int(color['b']*255)}, {color.get('a', 1)})",
                        "node_type": node.get("type"),
                        "node_name": node.get("name", "")
                    }
                    tokens.append(token)
        
        # Извлекаем strokes (обводки)
        if "strokes" in node and isinstance(node["strokes"], list):
            for stroke in node["strokes"]:
                if stroke.get("type") == "SOLID" and "color" in stroke:
                    color = stroke["color"]
                    token = {
                        "type": "color",
                        "name": "stroke_color",
                        "value": f"rgba({int(color['r']*255)}, {int(color['g']*255)}, {int(color['b']*255)}, {color.get('a', 1)})",
                        "node_type": node.get("type"),
                        "node_name": node.get("name", "")
                    }
                    tokens.append(token)
        
        # Извлекаем эффекты (тени)
        if "effects" in node and isinstance(node["effects"], list):
            for effect in node["effects"]:
                if effect.get("type") == "DROP_SHADOW":
                    shadow = effect
                    token = {
                        "type": "shadow",
                        "name": "shadow",
                        "value": {
                            "x": shadow.get("offset", {}).get("x", 0),
                            "y": shadow.get("offset", {}).get("y", 0),
                            "blur": shadow.get("radius", 0),
                            "color": shadow.get("color", {})
                        },
                        "node_type": node.get("type"),
                        "node_name": node.get("name", "")
                    }
                    tokens.append(token)
        
        # Рекурсивно обрабатываем детей
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                extract_from_node(child)
    
    extract_from_node(node_info)
    return tokens


async def _extract_tokens_from_file(file_key: str) -> List[Dict[str, Any]]:
    """Извлечение токенов из структуры файла."""
    tokens = []
    
    try:
        # Получаем информацию о файле
        file_info = await figma_api.get_file(file_key)
        
        # Извлекаем стили
        styles_data = await figma_api.get_styles(file_key)
        if "styles" in styles_data:
            for style in styles_data["styles"]:
                token_info = {
                    "type": "style",
                    "name": style.get("name", ""),
                    "style_type": style.get("styleType", ""),
                    "description": style.get("description", ""),
                    "key": style.get("key")
                }
                tokens.append(token_info)
        
        # Анализируем структуру документа для поиска повторяющихся значений
        document = file_info.get("document", {})
        _extract_tokens_from_document(document, tokens)
        
    except Exception as e:
        logger.error(f"Error extracting tokens from file: {e}")
    
    return tokens


def _extract_tokens_from_document(node: Dict[str, Any], tokens: List[Dict[str, Any]]):
    """Рекурсивное извлечение токенов из документа."""
    
    # Извлекаем цвета
    if "fills" in node and isinstance(node["fills"], list):
        for fill in node["fills"]:
            if fill.get("type") == "SOLID" and "color" in fill:
                color = fill["color"]
                color_value = f"rgba({int(color['r']*255)}, {int(color['g']*255)}, {int(color['b']*255)}, {color.get('a', 1)})"
                
                # Проверяем, есть ли уже такой цвет
                existing_token = next(
                    (t for t in tokens if t.get("type") == "color" and t.get("value") == color_value),
                    None
                )
                
                if not existing_token:
                    token = {
                        "type": "color",
                        "name": f"color_{len([t for t in tokens if t.get('type') == 'color'])}",
                        "value": color_value,
                        "source_node": node.get("name", ""),
                        "source_type": node.get("type", "")
                    }
                    tokens.append(token)
    
    # Рекурсивно обрабатываем детей
    if "children" in node and isinstance(node["children"], list):
        for child in node["children"]:
            _extract_tokens_from_document(child, tokens)


def _generate_import_path(component_name: str) -> str:
    """Генерация пути для импорта компонента."""
    # База знаний о путях импорта Kontur UI
    component_paths = {
        "button": "@skbkontur/react-ui/Button",
        "input": "@skbkontur/react-ui/Input",
        "textarea": "@skbkontur/react-ui/Textarea",
        "select": "@skbkontur/react-ui/Select",
        "checkbox": "@skbkontur/react-ui/Checkbox",
        "radio": "@skbkontur/react-ui/Radio",
        "switch": "@skbkontur/react-ui/Switch",
        "modal": "@skbkontur/react-ui/Modal",
        "dialog": "@skbkontur/react-ui/Dialog",
        "card": "@skbkontur/react-ui/Card",
        "table": "@skbkontur/react-ui/Table",
        "dropdown": "@skbkontur/react-ui/Dropdown",
        "tooltip": "@skbkontur/react-ui/Tooltip",
        "popup": "@skbkontur/react-ui/Popup",
        "tabs": "@skbkontur/react-ui/Tabs",
        "accordion": "@skbkontur/react-ui/Accordion",
        "badge": "@skbkontur/react-ui/Badge",
        "avatar": "@skbkontur/react-ui/Avatar",
        "icon": "@skbkontur/react-ui/Icon",
        "spinner": "@skbkontur/react-ui/Spinner",
        "progress": "@skbkontur/react-ui/Progress",
        "skeleton": "@skbkontur/react-ui/Skeleton",
        "alert": "@skbkontur/react-ui/Alert",
        "notification": "@skbkontur/react-ui/Notification",
        "breadcrumbs": "@skbkontur/react-ui/Breadcrumbs",
        "pagination": "@skbkontur/react-ui/Pagination",
        "stepper": "@skbkontur/react-ui/Stepper",
        "rating": "@skbkontur/react-ui/Rating",
        "slider": "@skbkontur/react-ui/Slider",
        "datepicker": "@skbkontur/react-ui/DatePicker",
        "timepicker": "@skbkontur/react-ui/TimePicker",
        "calendar": "@skbkontur/react-ui/Calendar",
        "tree": "@skbkontur/react-ui/Tree",
        "menu": "@skbkontur/react-ui/Menu",
        "navbar": "@skbkontur/react-ui/Navbar",
        "sidebar": "@skbkontur/react-ui/Sidebar",
        "footer": "@skbkontur/react-ui/Footer",
        "layout": "@skbkontur/react-ui/Layout",
        "grid": "@skbkontur/react-ui/Grid",
        "flex": "@skbkontur/react-ui/Flex",
        "stack": "@skbkontur/react-ui/Stack",
        "container": "@skbkontur/react-ui/Container",
        "paper": "@skbkontur/react-ui/Paper",
        "box": "@skbkontur/react-ui/Box",
        "form": "@skbkontur/react-ui/Form",
        "formgroup": "@skbkontur/react-ui/FormGroup",
        "formcontrol": "@skbkontur/react-ui/FormControl",
        "formlabel": "@skbkontur/react-ui/FormLabel",
        "formhelpertext": "@skbkontur/react-ui/FormHelperText",
        "formerrormessage": "@skbkontur/react-ui/FormErrorMessage",
    }
    
    # Приводим имя к нижнему регистру для поиска
    component_lower = component_name.lower()
    
    # Ищем точное совпадение
    for key, path in component_paths.items():
        if key in component_lower or component_lower in key:
            return path
    
    # Если точного совпадения нет, генерируем общий путь
    return f"@skbkontur/react-ui/{component_name}"


def _has_text_nodes(node: Dict[str, Any]) -> bool:
    """Проверяет, содержит ли нода текстовые элементы."""
    if node.get("type") == "TEXT":
        return True
    
    if "children" in node and isinstance(node["children"], list):
        for child in node["children"]:
            if _has_text_nodes(child):
                return True
    
    return False


def _has_image_nodes(node: Dict[str, Any]) -> bool:
    """Проверяет, содержит ли нода изображения."""
    if node.get("type") in ["RECTANGLE", "ELLIPSE", "VECTOR", "BOOLEAN_OPERATION"]:
        if "fills" in node and isinstance(node["fills"], list):
            for fill in node["fills"]:
                if fill.get("type") == "IMAGE":
                    return True
    
    if "children" in node and isinstance(node["children"], list):
        for child in node["children"]:
            if _has_image_nodes(child):
                return True
    
    return False


def _count_layers(node: Dict[str, Any]) -> int:
    """Считает количество слоев в ноде."""
    count = 1  # Текущая нода
    
    if "children" in node and isinstance(node["children"], list):
        for child in node["children"]:
            count += _count_layers(child)
    
    return count