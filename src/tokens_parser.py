"""Парсер для Tokens Studio данных."""
import json
from typing import Dict, Any, List, Optional
from metrics import logger

class TokensStudioParser:
    """Парсер для данных из Tokens Studio."""
    
    @staticmethod
    def parse_tokens_studio_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Парсинг данных из Tokens Studio в структурированный формат."""
        try:
            result = {
                "tokens": [],
                "components": [],
                "styles": [],
                "metadata": {}
            }
            
            # Парсинг токенов
            if "tokens" in raw_data:
                result["tokens"] = TokensStudioParser._parse_tokens(raw_data["tokens"])
            
            # Парсинг компонентов
            if "components" in raw_data:
                result["components"] = TokensStudioParser._parse_components(raw_data["components"])
            
            # Парсинг стилей
            if "styles" in raw_data:
                result["styles"] = TokensStudioParser._parse_styles(raw_data["styles"])
            
            # Метаданные
            if "metadata" in raw_data:
                result["metadata"] = raw_data["metadata"]
            
            logger.info(f"Parsed {len(result['components'])} components from Tokens Studio")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing Tokens Studio data: {e}")
            raise
    
    @staticmethod
    def _parse_tokens(tokens_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Парсинг токенов."""
        parsed_tokens = []
        
        for token_type, tokens in tokens_data.items():
            if isinstance(tokens, dict):
                for token_name, token_value in tokens.items():
                    parsed_tokens.append({
                        "type": token_type,
                        "name": token_name,
                        "value": token_value,
                        "full_name": f"{token_type}.{token_name}"
                    })
        
        return parsed_tokens
    
    @staticmethod
    def _parse_components(components_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Парсинг компонентов."""
        parsed_components = []
        
        for component_name, component_data in components_data.items():
            # Определяем тип компонента (component set или отдельный компонент)
            component_type = "component_set" if "variants" in component_data else "component"
            
            component_info = {
                "name": component_name,
                "type": component_type,
                "props": [],
                "variants": [],
                "tokens": []
            }
            
            # Парсинг пропсов
            if "props" in component_data:
                component_info["props"] = TokensStudioParser._parse_props(component_data["props"])
            
            # Парсинг вариантов
            if "variants" in component_data:
                component_info["variants"] = TokensStudioParser._parse_variants(component_data["variants"])
            
            # Парсинг токенов компонента
            if "tokens" in component_data:
                component_info["tokens"] = TokensStudioParser._parse_component_tokens(component_data["tokens"])
            
            parsed_components.append(component_info)
        
        return parsed_components
    
    @staticmethod
    def _parse_props(props_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Парсинг пропсов компонента."""
        parsed_props = []
        
        for prop_name, prop_info in props_data.items():
            prop_data = {
                "name": prop_name,
                "type": prop_info.get("type", "string"),
                "default_value": prop_info.get("default", ""),
                "required": prop_info.get("required", False),
                "description": prop_info.get("description", "")
            }
            
            # Обработка значений enum
            if "values" in prop_info:
                prop_data["values"] = prop_info["values"]
            
            parsed_props.append(prop_data)
        
        return parsed_props
    
    @staticmethod
    def _parse_variants(variants_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Парсинг вариантов компонента."""
        parsed_variants = []
        
        for variant_name, variant_data in variants_data.items():
            variant_info = {
                "name": variant_name,
                "props": variant_data.get("props", {}),
                "tokens": variant_data.get("tokens", {}),
                "description": variant_data.get("description", "")
            }
            parsed_variants.append(variant_info)
        
        return parsed_variants
    
    @staticmethod
    def _parse_component_tokens(tokens_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Парсинг токенов, связанных с компонентом."""
        component_tokens = []
        
        for token_type, tokens in tokens_data.items():
            if isinstance(tokens, dict):
                for token_name, token_value in tokens.items():
                    component_tokens.append({
                        "type": token_type,
                        "name": token_name,
                        "value": token_value
                    })
        
        return component_tokens
    
    @staticmethod
    def _parse_styles(styles_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Парсинг стилей."""
        parsed_styles = []
        
        for style_type, styles in styles_data.items():
            if isinstance(styles, dict):
                for style_name, style_value in styles.items():
                    parsed_styles.append({
                        "type": style_type,
                        "name": style_name,
                        "value": style_value,
                        "full_name": f"{style_type}.{style_name}"
                    })
        
        return parsed_styles
    
    @staticmethod
    def extract_component_metadata(component: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение метаданных компонента для использования агентом."""
        return {
            "component_name": component["name"],
            "props": component["props"],
            "variants": component["variants"],
            "import_path": f"@skbkontur/retail-ui/{component['name']}",
            "tokens_count": len(component.get("tokens", [])),
            "has_variants": len(component.get("variants", [])) > 0
        }