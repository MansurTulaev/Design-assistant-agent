"""Инструмент для сканирования Git-репозитория Retail UI и извлечения компонентов."""
from typing import Dict, Any, List, Optional
import os
import tempfile
import subprocess
import json
import time
import re  # Добавляем импорт re
from pathlib import Path
from mcp_instance import mcp
from metrics import (
    logger, TOOL_CALLS_TOTAL, TOOL_DURATION_SECONDS,
    COMPONENTS_SCANNED
)

# Конфигурация
RETAIL_UI_REPO_URL = "https://github.com/skbkontur/retail-ui"
DEFAULT_BRANCH = "master"
MAX_FILES_TO_SCAN = 1000

@mcp.tool()
async def scan_git_components(
    repo_url: str = RETAIL_UI_REPO_URL,
    branch: str = DEFAULT_BRANCH,
    include_props: bool = True,
    include_types: bool = True,
    include_docs: bool = True,
    max_files: int = MAX_FILES_TO_SCAN
) -> Dict[str, Any]:
    """
    Сканирование Git-репозитория Retail UI для извлечения информации о компонентах.
    
    Этот инструмент клонирует репозиторий Kontur UI (retail-ui) и анализирует
    исходный код TypeScript для извлечения информации о React компонентах,
    их пропсах, типах и документации. Полученные метаданные могут быть
    использованы агентом для понимания доступных компонентов при генерации кода.
    
    Args:
        repo_url (str): URL Git-репозитория Retail UI.
        branch (str): Ветка для сканирования.
        include_props (bool): Включить информацию о пропсах компонентов.
        include_types (bool): Включить TypeScript типы пропсов.
        include_docs (bool): Включить документацию из комментариев.
        max_files (int): Максимальное количество файлов для анализа.
        
    Returns:
        Dict[str, Any]: Структурированные данные о компонентах:
            - metadata: Метаданные сканирования
            - components: Список найденных компонентов
            - statistics: Статистика сканирования
            - import_paths: Пути для импорта компонентов
            
    Raises:
        ValueError: Если не удалось клонировать репозиторий.
        RuntimeError: Если не удалось проанализировать код.
        
    Examples:
        >>> scan_git_components()
        {
            "metadata": {
                "repo_url": "https://github.com/skbkontur/retail-ui",
                "branch": "master",
                "scan_timestamp": "2024-01-15T10:30:00Z",
                "components_found": 145
            },
            "components": [
                {
                    "name": "Button",
                    "file_path": "packages/react-ui/src/Button/Button.tsx",
                    "props": [
                        {"name": "variant", "type": "'primary' | 'secondary' | 'danger'"},
                        {"name": "size", "type": "'small' | 'medium' | 'large'"}
                    ],
                    "import_path": "@skbkontur/react-ui/Button",
                    "has_docs": true
                }
            ]
        }
        
    Note:
        - Требуется установленный Git в системе
        - Анализирует только TypeScript/TSX файлы
        - Извлекает информацию из экспортированных React компонентов
        - Поддерживает функциональные компоненты и классовые компоненты
    """
    
    start_time = time.time()
    tool_name = "scan_git_components"
    
    try:
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="started").inc()
        logger.info(f"Starting Git repository scan: {repo_url} (branch: {branch})")
        
        # Валидация входных данных
        if max_files <= 0:
            raise ValueError(f"max_files должен быть положительным числом, получено: {max_files}")
        
        if not repo_url.startswith(("http://", "https://", "git@")):
            raise ValueError(f"Некорректный URL репозитория: {repo_url}")
        
        # Создаем временную директорию для клонирования
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Cloning repository to temporary directory: {temp_dir}")
            
            # Клонируем репозиторий
            clone_success = await _clone_repository(repo_url, branch, temp_dir)
            if not clone_success:
                raise RuntimeError(f"Не удалось клонировать репозиторий: {repo_url}")
            
            # Анализируем репозиторий
            logger.info("Analyzing repository structure...")
            repo_info = await _analyze_repository_structure(temp_dir)
            
            # Ищем компоненты
            logger.info("Scanning for React components...")
            components = await _scan_for_components(
                temp_dir, 
                include_props, 
                include_types, 
                include_docs,
                max_files
            )
            
            # Формируем результаты
            results = {
                "metadata": {
                    "repo_url": repo_url,
                    "branch": branch,
                    "repo_name": _extract_repo_name(repo_url),
                    "clone_dir": temp_dir,
                    "scan_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "scan_options": {
                        "include_props": include_props,
                        "include_types": include_types,
                        "include_docs": include_docs,
                        "max_files": max_files
                    }
                },
                "repository_info": repo_info,
                "components": components,
                "import_paths": _generate_import_paths(components),
                "statistics": _calculate_statistics(components, repo_info),
                "errors": []
            }
            
            # Обновляем метаданные
            results["metadata"].update({
                "components_found": len(components),
                "scan_duration_seconds": round(time.time() - start_time, 2)
            })
            
            # Обновляем метрики
            COMPONENTS_SCANNED.set(len(components))
            TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="success").inc()
            TOOL_DURATION_SECONDS.labels(tool_name=tool_name).observe(time.time() - start_time)
            
            logger.info(f"Git scan completed: {len(components)} components found")
            
            return results
            
    except Exception as e:
        TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status="error").inc()
        logger.error(f"Error in scan_git_components: {e}")
        raise
    
    finally:
        duration = time.time() - start_time
        logger.debug(f"Tool {tool_name} executed in {duration:.2f} seconds")


async def _clone_repository(repo_url: str, branch: str, target_dir: str) -> bool:
    """Клонирование Git-репозитория."""
    try:
        # Проверяем, установлен ли Git
        git_check = subprocess.run(["git", "--version"], 
                                 capture_output=True, text=True)
        if git_check.returncode != 0:
            raise RuntimeError("Git не установлен в системе")
        
        # Клонируем репозиторий
        clone_cmd = [
            "git", "clone",
            "--branch", branch,
            "--depth", "1",  # Только последний коммит для скорости
            repo_url,
            target_dir
        ]
        
        logger.debug(f"Running git clone: {' '.join(clone_cmd)}")
        result = subprocess.run(
            clone_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 минут таймаут
        )
        
        if result.returncode != 0:
            logger.error(f"Git clone failed: {result.stderr}")
            return False
        
        logger.info(f"Repository cloned successfully to {target_dir}")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("Git clone timeout expired (5 minutes)")
        return False
    except Exception as e:
        logger.error(f"Error cloning repository: {e}")
        return False


async def _analyze_repository_structure(repo_dir: str) -> Dict[str, Any]:
    """Анализ структуры репозитория."""
    repo_path = Path(repo_dir)
    
    # Ищем package.json для получения информации о пакете
    package_json_path = repo_path / "package.json"
    package_info = {}
    if package_json_path.exists():
        try:
            with open(package_json_path, 'r', encoding='utf-8') as f:
                package_info = json.load(f)
        except Exception as e:
            logger.warning(f"Could not read package.json: {e}")
    
    # Анализируем структуру каталогов
    structure = {
        "total_files": 0,
        "typescript_files": 0,
        "tsx_files": 0,
        "mdx_files": 0,
        "directories": [],
        "package_info": {
            "name": package_info.get("name", "unknown"),
            "version": package_info.get("version", "unknown"),
            "description": package_info.get("description", ""),
            "dependencies": list(package_info.get("dependencies", {}).keys())[:10]  # первые 10
        }
    }
    
    # Рекурсивно обходим директории
    for root, dirs, files in os.walk(repo_dir):
        # Пропускаем скрытые директории и node_modules
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
        
        rel_root = os.path.relpath(root, repo_dir)
        if rel_root == ".":
            rel_root = ""
        
        dir_info = {
            "path": rel_root,
            "file_count": len(files),
            "file_types": {}
        }
        
        for file in files:
            structure["total_files"] += 1
            ext = os.path.splitext(file)[1].lower()
            
            if ext == '.ts':
                structure["typescript_files"] += 1
                dir_info["file_types"]["ts"] = dir_info["file_types"].get("ts", 0) + 1
            elif ext == '.tsx':
                structure["tsx_files"] += 1
                dir_info["file_types"]["tsx"] = dir_info["file_types"].get("tsx", 0) + 1
            elif ext == '.mdx':
                structure["mdx_files"] += 1
                dir_info["file_types"]["mdx"] = dir_info["file_types"].get("mdx", 0) + 1
        
        if dir_info["file_count"] > 0:
            structure["directories"].append(dir_info)
    
    # Сортируем директории по количеству файлов
    structure["directories"].sort(key=lambda x: x["file_count"], reverse=True)
    
    logger.info(f"Repository structure: {structure['total_files']} total files, "
                f"{structure['tsx_files']} TSX files")
    
    return structure


async def _scan_for_components(
    repo_dir: str,
    include_props: bool,
    include_types: bool,
    include_docs: bool,
    max_files: int
) -> List[Dict[str, Any]]:
    """Поиск и анализ React компонентов в репозитории."""
    components = []
    scanned_files = 0
    
    repo_path = Path(repo_dir)
    
    # Ищем TSX файлы (React компоненты обычно в .tsx)
    tsx_files = list(repo_path.rglob("*.tsx"))
    
    logger.info(f"Found {len(tsx_files)} TSX files to scan")
    
    for tsx_file in tsx_files[:max_files]:
        scanned_files += 1
        
        try:
            file_components = await _analyze_tsx_file(
                tsx_file, 
                repo_dir,
                include_props,
                include_types,
                include_docs
            )
            
            if file_components:
                components.extend(file_components)
                
        except Exception as e:
            logger.warning(f"Error analyzing file {tsx_file}: {e}")
            continue
    
    logger.info(f"Scanned {scanned_files} files, found {len(components)} components")
    return components


async def _analyze_tsx_file(
    file_path: Path,
    repo_dir: str,
    include_props: bool,
    include_types: bool,
    include_docs: bool
) -> List[Dict[str, Any]]:
    """Анализ одного TSX файла для поиска компонентов."""
    components = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Относительный путь от корня репозитория
        rel_path = str(file_path.relative_to(repo_dir))
        
        # Простой анализ для поиска экспортируемых компонентов
        # В реальной реализации здесь бы использовался парсер TypeScript AST
        
        # Ищем экспорт компонентов
        if "export" in content and ("function" in content or "const" in content):
            component_name = _extract_component_name(content, file_path.name)
            
            if component_name:
                component_info = {
                    "name": component_name,
                    "file_path": rel_path,
                    "file_name": file_path.name,
                    "is_function_component": "function" in content or "const" in content and "=>" in content,
                    "is_class_component": "class" in content and "extends" in content,
                    "has_default_export": "export default" in content,
                    "has_named_export": f"export {{ {component_name} }}" in content or f"export const {component_name}" in content,
                }
                
                # Извлекаем пропсы если нужно
                if include_props:
                    component_info["props"] = _extract_component_props(content, component_name)
                
                # Извлекаем TypeScript типы если нужно
                if include_types:
                    component_info["types"] = _extract_typescript_types(content)
                
                # Извлекаем документацию если нужно
                if include_docs:
                    component_info["docs"] = _extract_documentation(content, component_name)
                
                # Определяем путь для импорта
                component_info["import_path"] = _determine_import_path(component_name, rel_path)
                
                components.append(component_info)
    
    except Exception as e:
        logger.debug(f"Error analyzing file {file_path}: {e}")
    
    return components


def _extract_component_name(content: str, filename: str) -> Optional[str]:
    """Извлечение имени компонента из кода."""
    # Ищем export default компонент
    patterns = [
        r'export default function (\w+)',
        r'export default (\w+)',
        r'export const (\w+)',
        r'export function (\w+)',
        r'export class (\w+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    
    # Если не нашли по паттернам, пробуем из имени файла
    name_without_ext = os.path.splitext(filename)[0]
    if name_without_ext and name_without_ext[0].isupper():
        return name_without_ext
    
    return None


def _extract_component_props(content: str, component_name: str) -> List[Dict[str, Any]]:
    """Извлечение пропсов компонента."""
    props = []
    
    # Паттерны для поиска интерфейсов пропсов
    prop_patterns = [
        rf'interface {component_name}Props\s*{{([^}}]+)}}',
        rf'type {component_name}Props\s*=\s*{{([^}}]+)}}',
        rf'interface Props\s*{{([^}}]+)}}',  # Общий интерфейс Props
    ]
    
    for pattern in prop_patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            props_content = match.group(1)
            # Парсим свойства интерфейса
            prop_lines = props_content.split('\n')
            
            for line in prop_lines:
                line = line.strip()
                if line and not line.startswith('//') and not line.startswith('/*'):
                    # Упрощенный парсинг свойства
                    if ':' in line:
                        prop_name, prop_type = line.split(':', 1)
                        prop_name = prop_name.strip()
                        prop_type = prop_type.strip().rstrip(';')
                        
                        # Определяем обязательность
                        is_required = not prop_name.endswith('?')
                        if prop_name.endswith('?'):
                            prop_name = prop_name[:-1]
                        
                        prop_info = {
                            "name": prop_name,
                            "type": prop_type,
                            "required": is_required,
                            "description": _extract_prop_documentation(content, prop_name)
                        }
                        
                        # Пытаемся определить значения enum
                        if "'" in prop_type or '"' in prop_type:
                            # Это может быть union type с литералами
                            values = re.findall(r"['\"]([^'\"]+)['\"]", prop_type)
                            if values:
                                prop_info["values"] = values
                                prop_info["type"] = "enum"
                        
                        props.append(prop_info)
            
            break
    
    # Если не нашли интерфейс, ищем пропсы в аргументах функции
    if not props:
        func_pattern = rf'(?:function|const)\s+{component_name}\s*\(\s*([^)]*)\s*\)'
        match = re.search(func_pattern, content)
        if match:
            props_content = match.group(1).strip()
            # Простой парсинг деструктуризации пропсов
            if props_content.startswith('{') and props_content.endswith('}'):
                # Убираем фигурные скобки
                props_content = props_content[1:-1].strip()
                if props_content:
                    props_list = [p.strip() for p in props_content.split(',')]
                    for prop in props_list:
                        if prop:
                            # Обрабатываем деструктуризацию с дефолтными значениями
                            # Пример: { variant = "primary", size }
                            if '=' in prop:
                                prop_name = prop.split('=')[0].strip()
                            else:
                                prop_name = prop.strip()
                            
                            # Убираем возможные остаточные символы
                            prop_name = prop_name.replace('{', '').replace('}', '').strip()
                            
                            if prop_name:
                                prop_info = {
                                    "name": prop_name,
                                    "type": "any",
                                    "required": False,
                                    "description": ""
                                }
                                props.append(prop_info)
            elif props_content:  # Если пропсы передаются без деструктуризации
                # Пример: function Button(props) или function Button(props: ButtonProps)
                if ':' in props_content:
                    prop_name = props_content.split(':')[0].strip()
                    prop_type = props_content.split(':')[1].strip()
                    prop_info = {
                        "name": prop_name,
                        "type": prop_type,
                        "required": True,
                        "description": ""
                    }
                    props.append(prop_info)
                else:
                    # Просто имя переменной для пропсов
                    prop_info = {
                        "name": props_content,
                        "type": "any", 
                        "required": True,
                        "description": ""
                    }
                    props.append(prop_info)
    
    return props  # ВАЖНО: добавляем return


def _extract_typescript_types(content: str) -> Dict[str, Any]:
    """Извлечение TypeScript типов из файла."""
    types = {
        "interfaces": [],
        "types": [],
        "enums": []
    }
    
    # Ищем интерфейсы
    interfaces = re.findall(r'interface (\w+)\s*{([^}]+)}', content, re.DOTALL)
    for interface_name, interface_body in interfaces:
        types["interfaces"].append({
            "name": interface_name,
            "properties": _parse_interface_properties(interface_body)
        })
    
    # Ищем type aliases
    type_aliases = re.findall(r'type (\w+)\s*=\s*([^;]+);', content, re.DOTALL)
    for type_name, type_body in type_aliases:
        types["types"].append({
            "name": type_name,
            "definition": type_body.strip()
        })
    
    # Ищем enums
    enums = re.findall(r'enum (\w+)\s*{([^}]+)}', content, re.DOTALL)
    for enum_name, enum_body in enums:
        enum_values = [v.strip() for v in enum_body.split(',') if v.strip()]
        types["enums"].append({
            "name": enum_name,
            "values": enum_values
        })
    
    return types


def _parse_interface_properties(interface_body: str) -> List[Dict[str, Any]]:
    """Парсинг свойств интерфейса."""
    properties = []
    lines = interface_body.split('\n')
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('//') and not line.startswith('/*'):
            if ':' in line:
                prop_name, prop_type = line.split(':', 1)
                prop_name = prop_name.strip().rstrip('?')
                prop_type = prop_type.strip().rstrip(';')
                
                is_required = not line.strip().endswith('?')
                
                properties.append({
                    "name": prop_name,
                    "type": prop_type,
                    "required": is_required
                })
    
    return properties


def _extract_documentation(content: str, component_name: str) -> Dict[str, Any]:
    """Извлечение документации из комментариев."""
    docs = {
        "description": "",
        "examples": [],
        "notes": []
    }
    
    # Ищем JSDoc комментарии перед компонентом
    jsdoc_pattern = rf'/\*\*\s*\n([^*]|\*[^/])*\*/\s*(?:export\s+)?(?:default\s+)?(?:function|const|class)\s+{component_name}'
    match = re.search(jsdoc_pattern, content, re.DOTALL)
    
    if match:
        jsdoc = match.group(0)
        
        # Извлекаем описание
        description_match = re.search(r'\*\s+([^*\n]+)', jsdoc)
        if description_match:
            docs["description"] = description_match.group(1).strip()
        
        # Извлекаем примеры использования
        example_matches = re.findall(r'\*\s+@example\s+([^*\n]+)', jsdoc)
        docs["examples"] = [ex.strip() for ex in example_matches]
        
        # Извлекаем примечания
        note_matches = re.findall(r'\*\s+@note\s+([^*\n]+)', jsdoc)
        docs["notes"] = [note.strip() for note in note_matches]
    
    # Ищем однострочные комментарии
    single_line_comments = re.findall(r'//\s*([^\n]+)', content)
    if single_line_comments:
        docs["single_line_comments"] = [comment.strip() for comment in single_line_comments[:5]]  # первые 5
    
    return docs


def _extract_prop_documentation(content: str, prop_name: str) -> str:
    """Извлечение документации для конкретного пропса."""
    # Ищем комментарии перед пропсом
    pattern = rf'//\s*{prop_name}:\s*([^\n]+)|\*\s*{prop_name}:\s*([^*\n]+)'
    match = re.search(pattern, content)
    
    if match:
        return match.group(1) or match.group(2) or ""
    
    return ""


def _determine_import_path(component_name: str, file_path: str) -> str:
    """Определение пути для импорта компонента."""
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
    
    # Ищем точное совпадение
    component_lower = component_name.lower()
    for key, path in component_paths.items():
        if key in component_lower or component_lower in key:
            return path
    
    # Если не нашли, генерируем путь на основе структуры файла
    # Убираем расширения и index.tsx
    normalized_path = file_path.replace('src/', '').replace('index.tsx', '').replace('.tsx', '')
    if normalized_path.endswith('/'):
        normalized_path = normalized_path[:-1]
    
    return f"@skbkontur/react-ui/{normalized_path or component_name}"


def _extract_repo_name(repo_url: str) -> str:
    """Извлечение имени репозитория из URL."""
    # Пример: https://github.com/skbkontur/retail-ui -> retail-ui
    if '/' in repo_url:
        parts = repo_url.rstrip('/').split('/')
        if parts:
            return parts[-1].replace('.git', '')
    return repo_url


def _generate_import_paths(components: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Генерация структурированных путей импорта."""
    import_paths = {
        "by_component": {},
        "by_category": {
            "forms": [],
            "navigation": [],
            "layout": [],
            "feedback": [],
            "data_display": [],
            "overlays": []
        }
    }
    
    # Категории компонентов
    component_categories = {
        "forms": ["input", "textarea", "select", "checkbox", "radio", "switch", 
                 "form", "formgroup", "formcontrol", "formlabel"],
        "navigation": ["button", "menu", "tabs", "breadcrumbs", "pagination", 
                      "stepper", "navbar", "sidebar"],
        "layout": ["layout", "grid", "flex", "stack", "container", "card", 
                  "paper", "box", "footer"],
        "feedback": ["alert", "notification", "modal", "dialog", "tooltip", 
                    "popup", "spinner", "progress", "skeleton"],
        "data_display": ["table", "tree", "badge", "avatar", "icon", "rating", 
                        "calendar", "datepicker", "timepicker"],
        "overlays": ["dropdown", "tooltip", "popup", "modal", "dialog"]
    }
    
    for component in components:
        component_name = component["name"].lower()
        import_path = component.get("import_path", "")
        
        # Добавляем по имени компонента
        import_paths["by_component"][component["name"]] = import_path
        
        # Добавляем в категории
        for category, keywords in component_categories.items():
            if any(keyword in component_name for keyword in keywords):
                if import_path not in import_paths["by_category"][category]:
                    import_paths["by_category"][category].append(import_path)
    
    return import_paths


def _calculate_statistics(components: List[Dict[str, Any]], repo_info: Dict[str, Any]) -> Dict[str, Any]:
    """Расчет статистики сканирования."""
    stats = {
        "total_components": len(components),
        "components_with_props": 0,
        "components_with_docs": 0,
        "component_types": {
            "function_components": 0,
            "class_components": 0
        },
        "props_statistics": {
            "total_props": 0,
            "avg_props_per_component": 0,
            "required_props": 0,
            "optional_props": 0
        },
        "file_statistics": repo_info.get("package_info", {}).copy()
    }
    
    total_props = 0
    required_props = 0
    optional_props = 0
    
    for component in components:
        # Статистика по типам компонентов
        if component.get("is_function_component"):
            stats["component_types"]["function_components"] += 1
        if component.get("is_class_component"):
            stats["component_types"]["class_components"] += 1
        
        # Статистика по пропсам
        component_props = component.get("props", [])
        if component_props:
            stats["components_with_props"] += 1
            total_props += len(component_props)
            
            for prop in component_props:
                if prop.get("required"):
                    required_props += 1
                else:
                    optional_props += 1
        
        # Статистика по документации
        if component.get("docs") and component["docs"].get("description"):
            stats["components_with_docs"] += 1
    
    # Рассчитываем средние значения
    if components:
        stats["props_statistics"]["avg_props_per_component"] = round(total_props / len(components), 2)
    
    stats["props_statistics"].update({
        "total_props": total_props,
        "required_props": required_props,
        "optional_props": optional_props
    })
    
    # Дополнительная информация о репозитории
    stats["repository_files"] = {
        "total": repo_info.get("total_files", 0),
        "typescript": repo_info.get("typescript_files", 0),
        "tsx": repo_info.get("tsx_files", 0),
        "mdx": repo_info.get("mdx_files", 0)
    }
    
    return stats