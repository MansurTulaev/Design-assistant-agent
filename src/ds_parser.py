"""
Парсер дизайн-системы из TSX/TS файлов.
"""
import os
import ast
from typing import List, Dict, Optional
from dataclasses import dataclass
from .config import config

@dataclass
class ComponentProp:
    """Свойство компонента."""
    name: str
    type: str
    default: Optional[str] = None
    required: bool = False

@dataclass
class ComponentInfo:
    """Информация о React-компоненте."""
    name: str
    file_path: str
    props: List[ComponentProp]
    is_default_export: bool = False
    export_type: str = "function"

class DesignSystemParser:
    """Парсер дизайн-системы."""
    
    def __init__(self):
        self.supported_extensions = config.design_system.supported_extensions
        self.max_depth = config.design_system.max_depth
    
    def scan_directory(self, directory_path: str) -> List[ComponentInfo]:
        """Сканирует директорию на наличие React-компонентов."""
        if not os.path.exists(directory_path):
            raise ValueError(f"Директория не существует: {directory_path}")
        
        if not os.path.isdir(directory_path):
            raise ValueError(f"Указанный путь не является директорией: {directory_path}")
        
        components = []
        
        for root, _, files in os.walk(directory_path):
            current_depth = root[len(directory_path):].count(os.sep)
            if current_depth > self.max_depth:
                continue
            
            for file in files:
                if any(file.endswith(ext) for ext in self.supported_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        file_components = self.parse_file(file_path)
                        components.extend(file_components)
                    except (SyntaxError, UnicodeDecodeError):
                        continue
        
        return components
    
    def parse_file(self, file_path: str) -> List[ComponentInfo]:
        """Парсит один файл и извлекает информацию о компонентах."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._parse_with_ts_heuristics(content, file_path)
        
        components = []
        visitor = ComponentVisitor(file_path)
        visitor.visit(tree)
        
        return visitor.components
    
    def _parse_with_ts_heuristics(self, content: str, file_path: str) -> List[ComponentInfo]:
        """Эвристический парсинг TypeScript файлов."""
        import re
        components = []
        
        func_pattern = r"export\s+(?:default\s+)?(?:function|const)\s+(\w+)\s*[=:]\s*(?:\([^)]*\)\s*=>|function)"
        
        for match in re.finditer(func_pattern, content, re.MULTILINE | re.DOTALL):
            component_name = match.group(1)
            if component_name[0].isupper():
                components.append(ComponentInfo(
                    name=component_name,
                    file_path=file_path,
                    props=[],
                    is_default_export="default" in match.group(0),
                    export_type="function"
                ))
        
        return components

class ComponentVisitor(ast.NodeVisitor):
    """Посетитель AST для поиска React-компонентов."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.components = []
    
    def visit_FunctionDef(self, node):
        """Обрабатывает объявления функций."""
        if self._is_react_component(node):
            props = self._extract_props_from_function(node)
            
            self.components.append(ComponentInfo(
                name=node.name,
                file_path=self.file_path,
                props=props,
                is_default_export=self._is_default_export(node),
                export_type="function"
            ))
        
        self.generic_visit(node)
    
    def _is_react_component(self, node) -> bool:
        """Проверяет, является ли функция React-компонентом."""
        return node.name[0].isupper()
    
    def _extract_props_from_function(self, node) -> List[ComponentProp]:
        """Извлекает пропсы из объявления функции."""
        props = []
        
        for arg in node.args.args:
            if arg.arg == 'self':
                continue
                
            prop_type = "any"
            if arg.annotation:
                prop_type = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else "any"
            
            props.append(ComponentProp(
                name=arg.arg,
                type=prop_type,
                required=arg.annotation is not None
            ))
        
        return props
    
    def _is_default_export(self, node) -> bool:
        """Проверяет, является ли экспорт default."""
        return False