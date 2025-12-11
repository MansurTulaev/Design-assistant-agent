"""Вспомогательные функции для Figma MCP сервера."""
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from metrics import logger

def safe_json_parse(json_str: str, default: Any = None) -> Any:
    """Безопасный парсинг JSON строки."""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON: {e}")
        return default

def generate_component_id(component_name: str, component_key: str) -> str:
    """Генерация уникального ID для компонента."""
    hash_input = f"{component_name}_{component_key}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:8]

def flatten_figma_tree(node: Dict[str, Any], result: List[Dict[str, Any]] = None, 
                       parent_path: str = "") -> List[Dict[str, Any]]:
    """Преобразование иерархического дерева Figma в плоский список."""
    if result is None:
        result = []
    
    current_path = f"{parent_path}/{node.get('name', 'unnamed')}" if parent_path else node.get('name', 'unnamed')
    
    # Добавляем текущую ноду
    node_info = {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
        "path": current_path,
        "is_component": node.get("type") == "COMPONENT",
        "is_component_set": node.get("type") == "COMPONENT_SET",
        "is_instance": node.get("type") == "INSTANCE",
        "children_count": len(node.get("children", [])) if isinstance(node.get("children"), list) else 0
    }
    
    result.append(node_info)
    
    # Рекурсивно обрабатываем детей
    if "children" in node and isinstance(node["children"], list):
        for child in node["children"]:
            flatten_figma_tree(child, result, current_path)
    
    return result

def extract_component_properties(component_data: Dict[str, Any]) -> Dict[str, Any]:
    """Извлечение свойств компонента из данных Figma."""
    properties = {
        "name": component_data.get("name", ""),
        "description": component_data.get("description", ""),
        "key": component_data.get("key", ""),
        "props": [],
        "variants": [],
        "documentation_links": [],
        "created_at": component_data.get("createdAt", ""),
        "updated_at": component_data.get("updatedAt", "")
    }
    
    # Извлекаем свойства из componentProperties
    if "componentPropertyDefinitions" in component_data:
        props = component_data["componentPropertyDefinitions"]
        for prop_name, prop_info in props.items():
            prop_data = {
                "name": prop_name,
                "type": prop_info.get("type", "VARIANT"),
                "default_value": prop_info.get("defaultValue"),
                "variant_options": prop_info.get("variantOptions", [])
            }
            properties["props"].append(prop_data)
    
    # Извлекаем ссылки на документацию
    if "documentationLinks" in component_data and component_data["documentationLinks"]:
        properties["documentation_links"] = component_data["documentationLinks"]
    
    return properties

def format_react_component(component_name: str, props: List[Dict[str, Any]], 
                          import_path: str = "@skbkontur/react-ui") -> Dict[str, Any]:
    """Форматирование компонента для React."""
    # Генерация импорта
    import_statement = f'import {{ {component_name} }} from "{import_path}/{component_name}";'
    
    # Генерация пропсов для TypeScript
    prop_types = []
    for prop in props:
        prop_type = prop.get("type", "any").upper()
        if prop_type == "VARIANT":
            prop_type = "string"
        elif prop_type == "BOOLEAN":
            prop_type = "boolean"
        elif prop_type == "TEXT":
            prop_type = "string"
        
        prop_name = prop.get("name", "")
        default_value = prop.get("default_value", "")
        
        prop_types.append(f"  {prop_name}?: {prop_type};")
    
    # Генерация примера использования
    example_props = []
    for prop in props:
        prop_name = prop.get("name", "")
        default_value = prop.get("default_value", "")
        
        if default_value is not None and default_value != "":
            if prop.get("type") == "BOOLEAN":
                example_props.append(f"{prop_name}={{{str(default_value).lower()}}}")
            elif prop.get("type") == "TEXT":
                example_props.append(f'{prop_name}="{default_value}"')
            else:
                example_props.append(f'{prop_name}="{default_value}"')
    
    example_usage = f"<{component_name} {', '.join(example_props)} />" if example_props else f"<{component_name} />"
    
    return {
        "import_statement": import_statement,
        "prop_types": prop_types,
        "example_usage": example_usage,
        "component_name": component_name,
        "props_count": len(props)
    }

def calculate_similarity_score(figma_element: Dict[str, Any], 
                              design_system_component: Dict[str, Any]) -> float:
    """Расчет оценки схожести между элементом Figma и компонентом дизайн-системы."""
    score = 0.0
    max_score = 100.0
    
    # Сравнение по имени
    figma_name = figma_element.get("name", "").lower()
    component_name = design_system_component.get("name", "").lower()
    
    if component_name in figma_name or figma_name in component_name:
        score += 30.0
    elif any(word in figma_name for word in component_name.split()):
        score += 20.0
    
    # Сравнение по типу
    figma_type = figma_element.get("type", "")
    component_type = design_system_component.get("type", "")
    
    # Сопоставление типов Figma с типами компонентов
    type_mapping = {
        "TEXT": ["Input", "TextArea", "TextField"],
        "RECTANGLE": ["Button", "Card", "Container"],
        "FRAME": ["Modal", "Dialog", "Card"],
        "INSTANCE": ["Component"],
        "COMPONENT": ["Component"]
    }
    
    for figma_type_key, component_types in type_mapping.items():
        if figma_type == figma_type_key and any(ct in component_name for ct in component_types):
            score += 40.0
            break
    
    # Дополнительные факторы
    if figma_element.get("is_instance", False) and "instanceOf" in figma_element:
        score += 10.0
    
    if design_system_component.get("has_variants", False):
        score += 5.0
    
    # Нормализация оценки
    return min(score, max_score)

def create_mapping_report(figma_elements: List[Dict[str, Any]], 
                         design_system: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Создание отчета о сопоставлении элементов Figma с компонентами дизайн-системы."""
    mappings = []
    unmapped_elements = []
    
    for element in figma_elements:
        best_match = None
        best_score = 0.0
        
        for component in design_system:
            score = calculate_similarity_score(element, component)
            
            if score > best_score and score > 50.0:  # Пороговое значение
                best_score = score
                best_match = component
        
        if best_match:
            mappings.append({
                "figma_element": element,
                "design_system_component": best_match,
                "confidence_score": best_score,
                "recommended_import": format_react_component(
                    best_match["name"], 
                    best_match.get("props", [])
                )
            })
        else:
            unmapped_elements.append({
                "figma_element": element,
                "reason": "No suitable component found in design system",
                "suggestions": generate_component_suggestions(element)
            })
    
    return {
        "mappings": mappings,
        "unmapped_elements": unmapped_elements,
        "summary": {
            "total_elements": len(figma_elements),
            "successfully_mapped": len(mappings),
            "unmapped": len(unmapped_elements),
            "mapping_rate": f"{(len(mappings) / len(figma_elements) * 100):.1f}%" if figma_elements else "0%"
        }
    }

def generate_component_suggestions(figma_element: Dict[str, Any]) -> List[str]:
    """Генерация предложений по компонентам на основе элемента Figma."""
    element_type = figma_element.get("type", "")
    element_name = figma_element.get("name", "").lower()
    
    suggestions = []
    
    # База знаний о компонентах Kontur UI
    component_suggestions = {
        "TEXT": ["Input", "TextArea", "TextField", "Autocomplete"],
        "RECTANGLE": ["Button", "IconButton", "Toggle", "Checkbox", "Radio"],
        "FRAME": ["Modal", "Dialog", "Card", "Paper", "Popover"],
        "INSTANCE": ["Component from Kontur UI library"],
        "GROUP": ["Stack", "Grid", "Box", "Container"]
    }
    
    if element_type in component_suggestions:
        suggestions.extend(component_suggestions[element_type])
    
    # Дополнительные предложения на основе имени
    if "button" in element_name:
        suggestions.append("Button (primary, secondary, danger)")
    if "input" in element_name or "field" in element_name:
        suggestions.append("Input with label and validation")
    if "modal" in element_name or "dialog" in element_name:
        suggestions.append("Modal or Dialog component")
    if "card" in element_name:
        suggestions.append("Card with header and content")
    
    return list(set(suggestions))[:5]  # Убираем дубли и ограничиваем 5 предложениями

def timestamp() -> str:
    """Генерация временной метки."""
    return datetime.now().isoformat()

def log_operation(operation: str, details: Dict[str, Any]) -> None:
    """Логирование операции."""
    logger.info(f"{operation}: {json.dumps(details, ensure_ascii=False, default=str)}")