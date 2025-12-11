"""Валидаторы для Figma MCP сервера."""
import re
from typing import Optional
from metrics import MAX_FILE_SIZE, MAX_COMPONENTS, logger

def validate_figma_file_key(file_key: str) -> None:
    """Валидация ключа файла Figma."""
    if not file_key:
        raise ValueError("Ключ файла Figma не может быть пустым")
    
    # Figma file key обычно состоит из букв и цифр, длина 10-40 символов
    if not re.match(r'^[a-zA-Z0-9_-]{10,40}$', file_key):
        raise ValueError(f"Некорректный формат ключа файла Figma: {file_key}")
    
    logger.debug(f"Valid Figma file key: {file_key}")

def validate_figma_token(token: str) -> None:
    """Валидация токена Figma."""
    if not token:
        raise ValueError("Токен Figma не может быть пустым")
    
    # Figma токены начинаются с figd_
    if not token.startswith('figd_'):
        raise ValueError(f"Некорректный формат токена Figma. Должен начинаться с 'figd_'")
    
    if len(token) < 30:
        raise ValueError("Токен Figma слишком короткий")
    
    logger.debug("Valid Figma token provided")

def validate_component_limit(components_count: int) -> None:
    """Валидация количества компонентов."""
    if components_count > MAX_COMPONENTS:
        raise ValueError(
            f"Слишком много компонентов для обработки: {components_count}. "
            f"Максимально допустимое значение: {MAX_COMPONENTS}"
        )
    
    if components_count == 0:
        logger.warning("Файл не содержит компонентов")

def validate_node_data(node_data: dict, max_depth: int = 10) -> None:
    """Валидация данных ноды Figma."""
    if not node_data:
        raise ValueError("Данные ноды не могут быть пустыми")
    
    if "document" not in node_data:
        raise ValueError("Некорректные данные ноды: отсутствует поле 'document'")
    
    # Проверяем глубину дерева
    def check_depth(node: dict, current_depth: int, max_depth: int) -> None:
        if current_depth > max_depth:
            raise ValueError(f"Превышена максимальная глубина дерева: {max_depth}")
        
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                check_depth(child, current_depth + 1, max_depth)
    
    check_depth(node_data["document"], 1, max_depth)
    
    logger.debug(f"Valid node data with depth check passed (max_depth={max_depth})")

def validate_component_data(component_data: dict) -> None:
    """Валидация данных компонента."""
    if not component_data:
        raise ValueError("Данные компонента не могут быть пустыми")
    
    required_fields = ["key", "name", "description"]
    for field in required_fields:
        if field not in component_data:
            raise ValueError(f"Данные компонента не содержат обязательное поле: {field}")
    
    if not isinstance(component_data.get("name", ""), str) or not component_data["name"]:
        raise ValueError("Некорректное имя компонента")
    
    logger.debug(f"Valid component data: {component_data.get('name')}")

def validate_tokens_data(tokens_data: dict) -> None:
    """Валидация данных токенов."""
    if not tokens_data:
        raise ValueError("Данные токенов не могут быть пустыми")
    
    if not isinstance(tokens_data, dict):
        raise ValueError("Данные токенов должны быть словарем")
    
    # Проверяем структуру токенов
    expected_token_types = ["color", "typography", "spacing", "radius", "border", "shadow"]
    
    for token_type, tokens in tokens_data.items():
        if not isinstance(tokens, dict):
            raise ValueError(f"Токены типа '{token_type}' должны быть словарем")
        
        for token_name, token_value in tokens.items():
            if not isinstance(token_name, str) or not token_name:
                raise ValueError(f"Некорректное имя токена в типе '{token_type}'")
            
            # Проверяем значение токена в зависимости от типа
            if token_type == "color" and not is_valid_color_value(token_value):
                logger.warning(f"Некорректное значение цвета для токена {token_name}: {token_value}")
    
    logger.debug(f"Valid tokens data with {len(tokens_data)} token types")

def is_valid_color_value(color_value: str) -> bool:
    """Проверка валидности значения цвета."""
    if not isinstance(color_value, str):
        return False
    
    # Поддерживаемые форматы: HEX, RGB, RGBA, HSL, HSLA
    color_patterns = [
        r'^#[0-9A-Fa-f]{6}$',  # HEX
        r'^#[0-9A-Fa-f]{8}$',  # HEX с альфа-каналом
        r'^rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)$',  # RGB
        r'^rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*[\d\.]+\s*\)$',  # RGBA
        r'^hsl\(\s*\d+\s*,\s*\d+%\s*,\s*\d+%\s*\)$',  # HSL
        r'^hsla\(\s*\d+\s*,\s*\d+%\s*,\s*\d+%\s*,\s*[\d\.]+\s*\)$'  # HSLA
    ]
    
    return any(re.match(pattern, color_value.strip()) for pattern in color_patterns)

def validate_response_size(response_data: dict) -> None:
    """Валидация размера ответа от Figma API."""
    import json
    
    response_size = len(json.dumps(response_data).encode('utf-8'))
    
    if response_size > MAX_FILE_SIZE:
        raise ValueError(
            f"Размер ответа слишком большой: {response_size} байт. "
            f"Максимально допустимый размер: {MAX_FILE_SIZE} байт"
        )
    
    logger.debug(f"Response size validation passed: {response_size} bytes")

def validate_figma_response(response: dict, expected_fields: list = None) -> None:
    """Общая валидация ответа от Figma API."""
    if not response:
        raise ValueError("Пустой ответ от Figma API")
    
    if "error" in response:
        raise ValueError(f"Ошибка от Figma API: {response['error']}")
    
    if "status" in response and response["status"] != 200:
        raise ValueError(f"Некорректный статус ответа: {response['status']}")
    
    if expected_fields:
        for field in expected_fields:
            if field not in response:
                raise ValueError(f"Ответ не содержит ожидаемое поле: {field}")
    
    logger.debug("Valid Figma API response")