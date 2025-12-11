"""Инструмент для сопоставления макета Figma с компонентами дизайн-системы и генерации кода."""
from typing import Dict, Any, List, Optional, Tuple
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
    calculate_similarity_score, create_mapping_report,
    format_react_component, log_operation, timestamp
)
from validators import (
    validate_figma_file_key, validate_component_data,
    validate_response_size, validate_figma_response
)

# ID файлов по умолчанию
KONTUR_UI_FILE_ID = os.getenv("KONTUR_UI_FILE_ID", "KQc2jUV5CuCDqZ7hHTX0vc")
TEST_FILE_ID = os.getenv("TEST_FILE_ID", "d4qp6XOTZc3abUbq5UUDe7")

@mcp.tool
async def map_layout_to_components(
    layout_file_key: str = TEST_FILE_ID,
    design_system_file_key: str = KONTUR_UI_FILE_ID,
    generate_code: bool = True,
    include_imports: bool = True,
    include_typescript: bool = True,
    min_confidence: float = 60.0
) -> Dict[str, Any]:
    """
    Сопоставление элементов макета Figma с компонентами дизайн-системы и генерация React кода.
    
    Этот инструмент анализирует макет Figma, сопоставляет его элементы с компонентами
    из дизайн-системы Kontur UI и генерирует соответствующий React код. Инструмент
    используется агентом для автоматической генерации кода на основе дизайн-макетов.
    
    Args:
        layout_file_key (str): Ключ файла Figma с макетом для анализа.
        design_system_file_key (str): Ключ файла Figma с дизайн-системой Kontur UI.
        generate_code (bool): Генерировать React код на основе сопоставления.
        include_imports (bool): Включать импорты в сгенерированный код.
        include_typescript (bool): Генерировать TypeScript типы для пропсов.
        min_confidence (float): Минимальный уровень уверенности для сопоставления (0-100).
        
    Returns:
        Dict[str, Any]: Результаты сопоставления и генерации кода:
            - metadata: Метаданные сопоставления
            - design_system_summary: Краткая информация о дизайн-системе
            - layout_summary: Краткая информация о макете
            - mappings: Сопоставления элементов с компонентами
            - generated_code: Сгенерированный React код (если generate_code=True)
            - recommendations: Рекомендации по использованию компонентов
            - statistics: Статистика сопоставления
            
    Raises:
        ValueError: Если передан некорректный ключ файла или уровень уверенности.
        ConnectionError: Если не удалось подключиться к Figma API.
        
    Examples:
        >>> map_layout_to_components("d4qp6XOTZc3abUbq5UUDe7", "KQc2jUV5CuCDqZ7hHTX0vc")
        {
            "metadata": {
                "layout_file": "Login Form",
                "design_system_file": "Kontur UI Library",
                "mapping_timestamp": "2024-01-15T10:30:00Z",
                "mapping_success_rate": "85%"
            },
            "mappings": [
                {
                    "figma_element": {"name": "Email Input", "type": "INSTANCE"},
                    "matched_component": {"name": "Input", "import_path": "@skbkontur/react-ui/Input"},
                    "confidence": 92.5,
                    "props_mapping": {"label": "Email", "placeholder": "Enter your email"},
                    "generated_code": "<Input label=\"Email\" placeholder=\"Enter your email\" />"
                }
            ],
            "generated_code": {
                "imports": "import { Input, Button, Card } from '@skbkontur/react-ui';",
                "components": [
                    "<Card>\n  <Input label=\"Email\" />\n  <Button>Sign In</Button>\n</Card>"
                ]
            }
        }
        
    Note:
        - Для работы требуются доступы к обоим файлам Figma
        - Уровень уверенности (confidence) основан на схожести имен, типов и свойств
        - Генерация кода включает импорты и TypeScript типы по умолчанию
        - Рекомендуется использовать min_confidence=60.0 для баланса точности и покрытия
    """
    
    start_time = time.time()
    tool_name = "map_layout_to_components"
    
    try:
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="started").inc()
        logger.info(f"Starting component mapping: layout={layout_file_key}, design_system={design_system_file_key}")
        
        # Валидация входных данных
        validate_figma_file_key(layout_file_key)
        validate_figma_file_key(design_system_file_key)
        
        if not 0 <= min_confidence <= 100:
            raise ValueError(f"min_confidence должен быть в диапазоне 0-100, получено: {min_confidence}")
        
        if not figma_api:
            raise ConnectionError("Figma API не инициализирован. Проверьте токен доступа.")
        
        # Получаем информацию о файлах
        logger.info("Fetching file information...")
        layout_info = await figma_api.get_file(layout_file_key)
        design_system_info = await figma_api.get_file(design_system_file_key)
        
        validate_figma_response(layout_info, ["name", "document"])
        validate_figma_response(design_system_info, ["name", "document"])
        
        layout_name = layout_info.get("name", "Unknown Layout")
        design_system_name = design_system_info.get("name", "Unknown Design System")
        
        logger.info(f"Mapping layout '{layout_name}' to design system '{design_system_name}'")
        
        # Извлекаем компоненты из дизайн-системы
        logger.info("Extracting components from design system...")
        design_system_components = await _extract_design_system_components(design_system_file_key)
        
        # Извлекаем элементы из макета
        logger.info("Extracting elements from layout...")
        layout_elements = await _extract_layout_elements(layout_file_key)
        
        # Сопоставляем элементы с компонентами
        logger.info(f"Mapping {len(layout_elements)} elements to {len(design_system_components)} components...")
        mappings = await _map_elements_to_components(
            layout_elements, design_system_components, min_confidence
        )
        
        # Генерируем код, если требуется
        generated_code = None
        if generate_code and mappings["successfully_mapped"] > 0:
            logger.info("Generating React code...")
            generated_code = _generate_react_code(
                mappings["mappings"], include_imports, include_typescript
            )
        
        # Формируем результаты
        results = {
            "metadata": {
                "layout_file": layout_name,
                "layout_file_key": layout_file_key,
                "layout_file_url": f"https://www.figma.com/file/{layout_file_key}",
                "design_system_file": design_system_name,
                "design_system_file_key": design_system_file_key,
                "design_system_file_url": f"https://www.figma.com/file/{design_system_file_key}",
                "mapping_timestamp": timestamp(),
                "mapping_options": {
                    "generate_code": generate_code,
                    "include_imports": include_imports,
                    "include_typescript": include_typescript,
                    "min_confidence": min_confidence
                }
            },
            "design_system_summary": {
                "name": design_system_name,
                "components_count": len(design_system_components),
                "component_types": _analyze_component_types(design_system_components)
            },
            "layout_summary": {
                "name": layout_name,
                "elements_count": len(layout_elements),
                "element_types": _analyze_element_types(layout_elements)
            },
            "mappings": mappings,
            "generated_code": generated_code,
            "recommendations": _generate_recommendations(mappings, design_system_components),
            "statistics": _calculate_mapping_statistics(mappings, layout_elements, design_system_components),
            "errors": []
        }
        
        # Обновляем метаданные
        results["metadata"].update({
            "mapping_success_rate": f"{(mappings['successfully_mapped'] / len(layout_elements) * 100):.1f}%" if layout_elements else "0%",
            "mapping_duration_seconds": round(time.time() - start_time, 2),
            "errors_count": len(results["errors"])
        })
        
        # Обновляем метрики
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="success").inc()
        TOOL_DURATION_SECONDS.labels(tool_name=tool_name).observe(time.time() - start_time)
        
        logger.info(f"Component mapping completed: {mappings['successfully_mapped']}/{len(layout_elements)} elements mapped")
        
        # Валидация размера ответа
        validate_response_size(results)
        
        # Логируем операцию
        log_operation("map_layout_to_components", {
            "layout_file": layout_file_key,
            "design_system_file": design_system_file_key,
            "elements_mapped": mappings["successfully_mapped"],
            "total_elements": len(layout_elements),
            "success_rate": results["metadata"]["mapping_success_rate"],
            "duration": round(time.time() - start_time, 2)
        })
        
        return results
        
    except Exception as e:
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="error").inc()
        logger.error(f"Error in map_layout_to_components: {e}")
        raise
    
    finally:
        duration = time.time() - start_time
        logger.debug(f"Tool {tool_name} executed in {duration:.2f} seconds")


async def _extract_design_system_components(file_key: str) -> List[Dict[str, Any]]:
    """Извлечение компонентов из дизайн-системы."""
    components = []
    
    try:
        # Получаем все компоненты из файла
        components_data = await figma_api.get_components(file_key)
        if "components" in components_data:
            for component in components_data["components"]:
                # Получаем детальную информацию о компоненте
                nodes_data = await figma_api.get_file_nodes(file_key, [component["key"]])
                
                if "nodes" in nodes_data and component["key"] in nodes_data["nodes"]:
                    node_info = nodes_data["nodes"][component["key"]]["document"]
                    
                    component_info = {
                        "id": component.get("key"),
                        "name": component.get("name", "Unnamed"),
                        "description": component.get("description", ""),
                        "type": node_info.get("type"),
                        "props": extract_component_properties(node_info),
                        "is_main_component": node_info.get("type") == "COMPONENT",
                        "is_component_set": node_info.get("type") == "COMPONENT_SET",
                        "figma_url": f"https://www.figma.com/file/{file_key}/?node-id={component['key']}",
                        "tokens": _extract_component_tokens(node_info)
                    }
                    
                    # Извлекаем варианты для component sets
                    if component_info["is_component_set"] and "children" in node_info:
                        component_info["variants"] = _extract_component_variants(node_info)
                    
                    components.append(component_info)
        
        logger.info(f"Extracted {len(components)} components from design system")
        
    except Exception as e:
        logger.error(f"Error extracting design system components: {e}")
        raise
    
    return components


async def _extract_layout_elements(file_key: str) -> List[Dict[str, Any]]:
    """Извлечение элементов из макета."""
    elements = []
    
    try:
        # Получаем структуру файла
        file_info = await figma_api.get_file(file_key)
        document = file_info.get("document", {})
        
        # Рекурсивно извлекаем все элементы
        def extract_elements(node: Dict[str, Any], parent_path: str = ""):
            element_info = {
                "id": node.get("id"),
                "name": node.get("name", "Unnamed"),
                "type": node.get("type"),
                "path": f"{parent_path}/{node.get('name', '')}" if parent_path else node.get("name", ""),
                "bounding_box": node.get("absoluteBoundingBox"),
                "styles": _extract_element_styles(node),
                "is_component": node.get("type") == "COMPONENT",
                "is_instance": node.get("type") == "INSTANCE",
                "is_text": node.get("type") == "TEXT",
                "is_group": node.get("type") == "GROUP",
                "is_frame": node.get("type") == "FRAME"
            }
            
            # Добавляем информацию о текстовых элементах
            if element_info["is_text"]:
                element_info.update({
                    "text_content": node.get("characters", ""),
                    "text_style": _extract_text_style_info(node)
                })
            
            # Добавляем информацию о компонентах и экземплярах
            if element_info["is_instance"]:
                element_info.update({
                    "component_id": node.get("componentId"),
                    "component_properties": node.get("componentProperties", {})
                })
            
            elements.append(element_info)
            
            # Рекурсивно обрабатываем детей
            if "children" in node and isinstance(node["children"], list):
                for child in node["children"]:
                    extract_elements(child, element_info["path"])
        
        extract_elements(document)
        
        logger.info(f"Extracted {len(elements)} elements from layout")
        
    except Exception as e:
        logger.error(f"Error extracting layout elements: {e}")
        raise
    
    return elements


async def _map_elements_to_components(
    layout_elements: List[Dict[str, Any]],
    design_system_components: List[Dict[str, Any]],
    min_confidence: float
) -> Dict[str, Any]:
    """Сопоставление элементов макета с компонентами дизайн-системы."""
    
    mappings = []
    unmapped_elements = []
    
    # Фильтруем элементы, которые можно сопоставить
    mappable_elements = [
        elem for elem in layout_elements
        if elem.get("is_instance") or elem.get("is_text") or 
           elem.get("is_frame") or elem.get("type") in ["RECTANGLE", "ELLIPSE", "VECTOR"]
    ]
    
    logger.info(f"Mapping {len(mappable_elements)} mappable elements (from {len(layout_elements)} total)")
    
    for element in mappable_elements:
        best_match = None
        best_score = 0.0
        best_component = None
        
        # Ищем лучший подходящий компонент
        for component in design_system_components:
            score = calculate_similarity_score(element, component)
            
            if score > best_score and score >= min_confidence:
                best_score = score
                best_match = component
        
        if best_match and best_score >= min_confidence:
            # Создаем сопоставление
            mapping = _create_mapping(element, best_match, best_score)
            mappings.append(mapping)
        else:
            # Элемент не удалось сопоставить
            unmapped_elements.append({
                "element": element,
                "best_score": best_score if best_match else 0.0,
                "reason": "No component meets minimum confidence" if best_match else "No suitable component found",
                "suggestions": _generate_element_suggestions(element, design_system_components)
            })
    
    # Группируем сопоставления по компонентам
    component_mappings = {}
    for mapping in mappings:
        component_name = mapping["matched_component"]["name"]
        if component_name not in component_mappings:
            component_mappings[component_name] = []
        component_mappings[component_name].append(mapping)
    
    return {
        "mappings": mappings,
        "unmapped_elements": unmapped_elements,
        "component_mappings": component_mappings,
        "successfully_mapped": len(mappings),
        "total_mappable_elements": len(mappable_elements),
        "mapping_rate": f"{(len(mappings) / len(mappable_elements) * 100):.1f}%" if mappable_elements else "0%",
        "average_confidence": round(
            sum(m["confidence"] for m in mappings) / len(mappings) if mappings else 0, 2
        )
    }


def _create_mapping(
    element: Dict[str, Any],
    component: Dict[str, Any],
    confidence: float
) -> Dict[str, Any]:
    """Создание сопоставления элемента с компонентом."""
    
    # Определяем пропсы на основе элемента
    props_mapping = _determine_props_mapping(element, component)
    
    # Генерируем пример кода
    example_code = _generate_component_example(component, props_mapping)
    
    mapping = {
        "figma_element": {
            "id": element.get("id"),
            "name": element.get("name"),
            "type": element.get("type"),
            "path": element.get("path"),
            "is_instance": element.get("is_instance", False),
            "is_text": element.get("is_text", False)
        },
        "matched_component": {
            "name": component.get("name"),
            "type": component.get("type"),
            "description": component.get("description", ""),
            "import_path": _determine_import_path(component),
            "props_count": len(component.get("props", [])),
            "has_variants": len(component.get("variants", [])) > 0
        },
        "confidence": confidence,
        "props_mapping": props_mapping,
        "example_code": example_code,
        "mapping_notes": _generate_mapping_notes(element, component, props_mapping)
    }
    
    # Добавляем текстовый контент для текстовых элементов
    if element.get("is_text"):
        mapping["figma_element"]["text_content"] = element.get("text_content", "")
    
    # Добавляем свойства компонента для экземпляров
    if element.get("is_instance") and element.get("component_properties"):
        mapping["figma_element"]["component_properties"] = element["component_properties"]
    
    return mapping


def _determine_props_mapping(
    element: Dict[str, Any],
    component: Dict[str, Any]
) -> Dict[str, Any]:
    """Определение пропсов на основе элемента."""
    props_mapping = {}
    
    # Если это экземпляр компонента, используем его свойства
    if element.get("is_instance") and element.get("component_properties"):
        props_mapping.update(element["component_properties"])
    
    # Для текстовых элементов добавляем текст как children или value
    if element.get("is_text") and element.get("text_content"):
        component_props = component.get("props", [])
        
        # Проверяем, есть ли у компонента пропс для текста
        text_prop_names = ["value", "text", "children", "label", "placeholder", "title"]
        for prop in component_props:
            prop_name = prop.get("name", "").lower()
            if prop_name in text_prop_names:
                props_mapping[prop["name"]] = element["text_content"]
                break
        else:
            # Если не нашли подходящий пропс, используем children
            props_mapping["children"] = element["text_content"]
    
    # Для кнопок и подобных элементов
    element_name = element.get("name", "").lower()
    if any(keyword in element_name for keyword in ["button", "btn", "submit", "confirm"]):
        # Проверяем тип кнопки
        if "primary" in element_name:
            props_mapping["variant"] = "primary"
        elif "secondary" in element_name:
            props_mapping["variant"] = "secondary"
        elif "danger" in element_name or "delete" in element_name:
            props_mapping["variant"] = "danger"
        
        # Проверяем размер
        if "large" in element_name or "big" in element_name:
            props_mapping["size"] = "large"
        elif "small" in element_name or "sm" in element_name:
            props_mapping["size"] = "small"
    
    # Для полей ввода
    if any(keyword in element_name for keyword in ["input", "field", "textfield"]):
        if "email" in element_name:
            props_mapping["type"] = "email"
            props_mapping["label"] = "Email"
            props_mapping["placeholder"] = "Enter your email"
        elif "password" in element_name:
            props_mapping["type"] = "password"
            props_mapping["label"] = "Password"
            props_mapping["placeholder"] = "Enter your password"
        elif "search" in element_name:
            props_mapping["placeholder"] = "Search..."
    
    return props_mapping


def _determine_import_path(component: Dict[str, Any]) -> str:
    """Определение пути для импорта компонента."""
    component_name = component.get("name", "")
    
    # База знаний о путях импорта Kontur UI
    import_paths = {
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
    
    # Ищем совпадение (частичное или полное)
    component_lower = component_name.lower()
    for key, path in import_paths.items():
        if key in component_lower or component_lower in key:
            return path
    
    # Если не нашли, генерируем общий путь
    return f"@skbkontur/react-ui/{component_name}"


def _generate_component_example(
    component: Dict[str, Any],
    props_mapping: Dict[str, Any]
) -> str:
    """Генерация примера кода для компонента."""
    component_name = component.get("name", "Component")
    
    # Форматируем пропсы
    props_str = ""
    if props_mapping:
        props_items = []
        for key, value in props_mapping.items():
            if isinstance(value, str):
                props_items.append(f'{key}="{value}"')
            elif isinstance(value, bool):
                props_items.append(f'{key}={{{str(value).lower()}}}')
            else:
                props_items.append(f'{key}={{{value}}}')
        
        if props_items:
            props_str = " " + " ".join(props_items)
    
    return f"<{component_name}{props_str} />"


def _generate_mapping_notes(
    element: Dict[str, Any],
    component: Dict[str, Any],
    props_mapping: Dict[str, Any]
) -> List[str]:
    """Генерация заметок о сопоставлении."""
    notes = []
    
    # Проверяем, является ли элемент экземпляром
    if element.get("is_instance"):
        notes.append("Element is an instance of a Figma component")
    
    # Проверяем пропсы
    component_props = component.get("props", [])
    mapped_props = set(props_mapping.keys())
    component_prop_names = {prop.get("name") for prop in component_props}
    
    # Проверяем неподдерживаемые пропсы
    unsupported_props = mapped_props - component_prop_names
    if unsupported_props:
        notes.append(f"Note: Some mapped props may not be supported by component: {', '.join(unsupported_props)}")
    
    # Проверяем обязательные пропсы
    required_props = {prop.get("name") for prop in component_props if prop.get("required", False)}
    missing_required = required_props - mapped_props
    if missing_required:
        notes.append(f"Warning: Missing required props: {', '.join(missing_required)}")
    
    return notes


def _generate_element_suggestions(
    element: Dict[str, Any],
    components: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Генерация предложений для несопоставленного элемента."""
    suggestions = []
    
    # Сортируем компоненты по схожести
    scored_components = []
    for component in components:
        score = calculate_similarity_score(element, component)
        scored_components.append((score, component))
    
    # Берем топ-3 наиболее подходящих компонента
    scored_components.sort(reverse=True, key=lambda x: x[0])
    top_components = scored_components[:3]
    
    for score, component in top_components:
        if score > 30:  # Минимальный порог для предложения
            suggestions.append({
                "component": component.get("name"),
                "confidence": score,
                "reason": _get_suggestion_reason(element, component, score),
                "example": _generate_component_example(component, {})
            })
    
    return suggestions


def _get_suggestion_reason(
    element: Dict[str, Any],
    component: Dict[str, Any],
    score: float
) -> str:
    """Получение причины для предложения компонента."""
    element_name = element.get("name", "").lower()
    component_name = component.get("name", "").lower()
    
    reasons = []
    
    # Проверяем совпадение по имени
    if component_name in element_name or element_name in component_name:
        reasons.append("name similarity")
    
    # Проверяем тип элемента
    element_type = element.get("type", "")
    if element_type == "TEXT" and any(keyword in component_name for keyword in ["input", "textarea", "textfield"]):
        reasons.append("text element matches input component")
    elif element_type in ["RECTANGLE", "FRAME"] and "button" in component_name:
        reasons.append("rectangular element matches button component")
    elif element_type == "INSTANCE":
        reasons.append("instance of a Figma component")
    
    if not reasons:
        reasons.append(f"partial match (score: {score})")
    
    return ", ".join(reasons)


def _generate_react_code(
    mappings: List[Dict[str, Any]],
    include_imports: bool,
    include_typescript: bool
) -> Dict[str, Any]:
    """Генерация React кода на основе сопоставлений."""
    
    # Группируем по компонентам
    components_by_type = {}
    for mapping in mappings:
        component_name = mapping["matched_component"]["name"]
        if component_name not in components_by_type:
            components_by_type[component_name] = []
        components_by_type[component_name].append(mapping)
    
    # Генерируем импорты
    imports = set()
    component_code = []
    typescript_interfaces = []
    
    for component_name, component_mappings in components_by_type.items():
        # Добавляем импорт
        import_path = component_mappings[0]["matched_component"]["import_path"]
        imports.add(import_path)
        
        # Генерируем код для каждого использования
        for i, mapping in enumerate(component_mappings):
            component_code.append({
                "id": mapping["figma_element"]["id"],
                "name": mapping["figma_element"]["name"],
                "code": mapping["example_code"],
                "props": mapping["props_mapping"]
            })
        
        # Генерируем TypeScript интерфейс, если нужно
        if include_typescript:
            interface_code = _generate_typescript_interface(component_name, component_mappings[0])
            typescript_interfaces.append(interface_code)
    
    # Форматируем импорты
    import_statements = []
    for import_path in sorted(imports):
        # Извлекаем имя компонента из пути
        component_name = import_path.split("/")[-1]
        import_statements.append(f"import {{ {component_name} }} from '{import_path}';")
    
    # Собираем результаты
    result = {
        "imports": import_statements if include_imports else [],
        "components": component_code,
        "typescript_interfaces": typescript_interfaces if include_typescript else [],
        "total_components": len(components_by_type),
        "total_usages": len(mappings)
    }
    
    # Генерируем полный пример компонента
    if component_code:
        result["example_component"] = _generate_example_component(component_code, import_statements)
    
    return result


def _generate_typescript_interface(
    component_name: str,
    mapping: Dict[str, Any]
) -> str:
    """Генерация TypeScript интерфейса для компонента."""
    component_info = mapping["matched_component"]
    
    interface_lines = []
    interface_lines.append(f"interface {component_name}Props {{")
    
    # Добавляем пропсы из компонента
    for prop in component_info.get("props", []):
        prop_name = prop.get("name", "")
        prop_type = prop.get("type", "any")
        
        # Конвертируем тип Figma в TypeScript
        ts_type = _convert_figma_type_to_ts(prop_type)
        
        # Определяем, обязательный ли пропс
        is_required = prop.get("required", False)
        optional_marker = "" if is_required else "?"
        
        # Добавляем дефолтное значение
        default_value = prop.get("default_value")
        comment = ""
        if default_value is not None:
            comment = f" // default: {default_value}"
        
        interface_lines.append(f"  {prop_name}{optional_marker}: {ts_type};{comment}")
    
    # Добавляем стандартные React пропсы
    interface_lines.append("  className?: string;")
    interface_lines.append("  style?: React.CSSProperties;")
    interface_lines.append("  children?: React.ReactNode;")
    
    interface_lines.append("}")
    
    return "\n".join(interface_lines)


def _convert_figma_type_to_ts(figma_type: str) -> str:
    """Конвертация типа Figma в TypeScript."""
    type_mapping = {
        "BOOLEAN": "boolean",
        "TEXT": "string",
        "VARIANT": "string",
        "INSTANCE_SWAP": "string",
        "NUMBER": "number"
    }
    
    return type_mapping.get(figma_type.upper(), "any")


def _generate_example_component(
    component_code: List[Dict[str, Any]],
    import_statements: List[str]
) -> str:
    """Генерация полного примера React компонента."""
    lines = []
    
    # Добавляем импорты
    if import_statements:
        lines.extend(import_statements)
        lines.append("")
    
    # Добавляем компонент
    lines.append("const GeneratedComponent = () => {")
    lines.append("  return (")
    lines.append("    <div>")
    
    # Добавляем использование компонентов
    for code_info in component_code:
        lines.append(f"      {code_info['code']}")
    
    lines.append("    </div>")
    lines.append("  );")
    lines.append("};")
    lines.append("")
    lines.append("export default GeneratedComponent;")
    
    return "\n".join(lines)


def _generate_recommendations(
    mappings: Dict[str, Any],
    design_system_components: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Генерация рекомендаций по использованию компонентов."""
    recommendations = []
    
    # Анализируем наиболее часто используемые компоненты
    component_usage = {}
    for mapping in mappings["mappings"]:
        component_name = mapping["matched_component"]["name"]
        component_usage[component_name] = component_usage.get(component_name, 0) + 1
    
    # Рекомендуем часто используемые компоненты
    if component_usage:
        most_used = max(component_usage.items(), key=lambda x: x[1])
        recommendations.append({
            "type": "most_used_component",
            "component": most_used[0],
            "usage_count": most_used[1],
            "message": f"'{most_used[0]}' is the most frequently used component in this layout"
        })
    
    # Рекомендуем компоненты для несопоставленных элементов
    if mappings["unmapped_elements"]:
        recommendations.append({
            "type": "unmapped_elements",
            "count": len(mappings["unmapped_elements"]),
            "message": f"{len(mappings['unmapped_elements'])} elements couldn't be mapped. Consider creating custom components or extending the design system."
        })
    
    # Рекомендуем проверку обязательных пропсов
    missing_required_count = 0
    for mapping in mappings["mappings"]:
        notes = mapping.get("mapping_notes", [])
        for note in notes:
            if "Missing required props" in note:
                missing_required_count += 1
    
    if missing_required_count > 0:
        recommendations.append({
            "type": "missing_required_props",
            "count": missing_required_count,
            "message": f"{missing_required_count} components are missing required props. Please review the generated code."
        })
    
    return recommendations


def _calculate_mapping_statistics(
    mappings: Dict[str, Any],
    layout_elements: List[Dict[str, Any]],
    design_system_components: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Расчет статистики сопоставления."""
    
    # Распределение уверенности
    confidence_distribution = {"high": 0, "medium": 0, "low": 0}
    for mapping in mappings["mappings"]:
        confidence = mapping["confidence"]
        if confidence >= 80:
            confidence_distribution["high"] += 1
        elif confidence >= 60:
            confidence_distribution["medium"] += 1
        else:
            confidence_distribution["low"] += 1
    
    # Типы сопоставленных элементов
    element_type_distribution = {}
    for mapping in mappings["mappings"]:
        element_type = mapping["figma_element"]["type"]
        element_type_distribution[element_type] = element_type_distribution.get(element_type, 0) + 1
    
    # Пропсы в сопоставлениях
    total_props_mapped = 0
    for mapping in mappings["mappings"]:
        total_props_mapped += len(mapping.get("props_mapping", {}))
    
    return {
        "total_elements": len(layout_elements),
        "mappable_elements": mappings["total_mappable_elements"],
        "successfully_mapped": mappings["successfully_mapped"],
        "mapping_rate_percent": float(mappings["mapping_rate"].rstrip("%")),
        "average_confidence": mappings["average_confidence"],
        "confidence_distribution": confidence_distribution,
        "element_type_distribution": element_type_distribution,
        "unique_components_used": len(mappings.get("component_mappings", {})),
        "total_props_mapped": total_props_mapped,
        "avg_props_per_mapping": round(total_props_mapped / len(mappings["mappings"]) if mappings["mappings"] else 0, 2),
        "design_system_coverage": round((len(mappings.get("component_mappings", {})) / len(design_system_components) * 100) if design_system_components else 0, 1)
    }


def _extract_component_tokens(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Извлечение токенов из компонента."""
    tokens = []
    
    def extract_from_node(current_node: Dict[str, Any]):
        # Извлекаем fills
        if "fills" in current_node and isinstance(current_node["fills"], list):
            for fill in current_node["fills"]:
                if fill.get("type") == "SOLID" and "color" in fill:
                    color = fill["color"]
                    tokens.append({
                        "type": "color",
                        "usage": "fill",
                        "value": f"rgba({int(color['r']*255)}, {int(color['g']*255)}, {int(color['b']*255)}, {color.get('a', 1)})"
                    })
        
        # Извлекаем strokes
        if "strokes" in current_node and isinstance(current_node["strokes"], list):
            for stroke in current_node["strokes"]:
                if stroke.get("type") == "SOLID" and "color" in stroke:
                    color = stroke["color"]
                    tokens.append({
                        "type": "color",
                        "usage": "stroke",
                        "value": f"rgba({int(color['r']*255)}, {int(color['g']*255)}, {int(color['b']*255)}, {color.get('a', 1)})"
                    })
        
        # Рекурсивно обрабатываем детей
        if "children" in current_node and isinstance(current_node["children"], list):
            for child in current_node["children"]:
                extract_from_node(child)
    
    extract_from_node(node)
    return tokens


def _extract_component_variants(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Извлечение вариантов компонента."""
    variants = []
    
    if "children" in node and isinstance(node["children"], list):
        for child in node["children"]:
            if child.get("type") == "COMPONENT":
                variant_info = {
                    "name": child.get("name", "Unnamed"),
                    "id": child.get("id"),
                    "props": child.get("componentProperties", {}),
                    "tokens": _extract_component_tokens(child)
                }
                variants.append(variant_info)
    
    return variants


def _extract_element_styles(node: Dict[str, Any]) -> Dict[str, Any]:
    """Извлечение стилей элемента."""
    styles = {
        "fills": [],
        "strokes": [],
        "effects": [],
        "opacity": node.get("opacity", 1)
    }
    
    # Извлекаем fills
    if "fills" in node and isinstance(node["fills"], list):
        for fill in node["fills"]:
            if fill.get("type") == "SOLID" and "color" in fill:
                color = fill["color"]
                styles["fills"].append({
                    "type": "solid",
                    "color": f"rgba({int(color['r']*255)}, {int(color['g']*255)}, {int(color['b']*255)}, {color.get('a', 1)})"
                })
    
    # Извлекаем strokes
    if "strokes" in node and isinstance(node["strokes"], list):
        for stroke in node["strokes"]:
            if stroke.get("type") == "SOLID" and "color" in stroke:
                color = stroke["color"]
                styles["strokes"].append({
                    "type": "solid",
                    "color": f"rgba({int(color['r']*255)}, {int(color['g']*255)}, {int(color['b']*255)}, {color.get('a', 1)})"
                })
    
    return styles


def _extract_text_style_info(node: Dict[str, Any]) -> Dict[str, Any]:
    """Извлечение информации о текстовом стиле."""
    style_info = {
        "font_family": "Unknown",
        "font_size": 14,
        "color": "#000000"
    }
    
    if "style" in node:
        style = node["style"]
        
        if "fontFamily" in style:
            style_info["font_family"] = style["fontFamily"]
        
        if "fontSize" in style:
            style_info["font_size"] = style["fontSize"]
        
        if "fills" in node and isinstance(node["fills"], list):
            for fill in node["fills"]:
                if fill.get("type") == "SOLID" and "color" in fill:
                    color = fill["color"]
                    style_info["color"] = f"rgba({int(color['r']*255)}, {int(color['g']*255)}, {int(color['b']*255)}, {color.get('a', 1)})"
                    break
    
    return style_info


def _analyze_component_types(components: List[Dict[str, Any]]) -> Dict[str, int]:
    """Анализ типов компонентов в дизайн-системе."""
    type_distribution = {}
    
    for component in components:
        component_type = component.get("type", "unknown")
        type_distribution[component_type] = type_distribution.get(component_type, 0) + 1
    
    return type_distribution


def _analyze_element_types(elements: List[Dict[str, Any]]) -> Dict[str, int]:
    """Анализ типов элементов в макете."""
    type_distribution = {}
    
    for element in elements:
        element_type = element.get("type", "unknown")
        type_distribution[element_type] = type_distribution.get(element_type, 0) + 1
    
    return type_distribution