"""
Инструмент для анализа дизайн-системы из TSX/TS/JS/JSX файлов.
"""

import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from ..mcp_instance import mcp, TOOL_CALLS_TOTAL

# ---------------------------------------------------------------------
# DATACLASS
# ---------------------------------------------------------------------
@dataclass
class ComponentProp:
    name: str
    type: str
    default: Optional[str] = None
    required: bool = False

@dataclass
class ComponentInfo:
    name: str
    file_path: str
    props: List[ComponentProp]
    is_default_export: bool = False
    export_type: str = "function"

# ---------------------------------------------------------------------
# PARSER
# ---------------------------------------------------------------------
class DesignSystemParser:
    """Парсер дизайн-системы для TSX/TS/JS/JSX файлов."""

    def __init__(self, supported_extensions=None, max_depth=10):
        if supported_extensions is None:
            supported_extensions = [".tsx", ".ts", ".jsx", ".js"]
        self.supported_extensions = tuple(supported_extensions)
        self.max_depth = max_depth

    def scan_directory(self, directory_path: str) -> List[ComponentInfo]:
        """Рекурсивно сканирует директорию на наличие компонентов."""
        if not os.path.isdir(directory_path):
            raise ValueError(f"Путь не является директорией: {directory_path}")

        components = []
        for root, _, files in os.walk(directory_path):
            current_depth = root[len(directory_path):].count(os.sep)
            if current_depth > self.max_depth:
                continue

            for file in files:
                if file.endswith(self.supported_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        comps = self.parse_file(file_path)
                        components.extend(comps)
                    except Exception:
                        continue
        return components

    def parse_file(self, file_path: str) -> List[ComponentInfo]:
        """Парсит один файл через regex эвристику."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        components = []

        # Паттерн: export default function X(...) или export function X(...)
        func_export_pattern = r"export\s+(default\s+)?function\s+(\w+)\s*\(([^)]*)\)"
        # Паттерн: const X: FC<Props> = (...) => ...  или const X = (...) => ...
        const_pattern = r"export\s+(default\s+)?const\s+(\w+)\s*(?::\s*[^=]+)?=\s*\(?([^)]*)\)?\s*=>"

        for pattern, exp_type in [(func_export_pattern, "function"), (const_pattern, "arrow")]:
            for match in re.finditer(pattern, content, re.MULTILINE):
                name = match.group(2)
                if not name or not name[0].isupper():
                    continue
                props_str = match.group(3)
                props = self._parse_props(props_str)
                is_default = bool(match.group(1))
                components.append(ComponentInfo(
                    name=name,
                    file_path=file_path,
                    props=props,
                    is_default_export=is_default,
                    export_type=exp_type
                ))
        return components

    def _parse_props(self, props_str: str) -> List[ComponentProp]:
        """Простейший разбор аргументов функции на пропсы."""
        props = []
        if not props_str.strip():
            return props

        for part in props_str.split(','):
            part = part.strip()
            if not part:
                continue
            if ':' in part:
                name, type_ = map(str.strip, part.split(':', 1))
                required = not type_.endswith('?')
            else:
                name = part
                type_ = "any"
                required = True
            props.append(ComponentProp(name=name, type=type_, required=required))
        return props

# ---------------------------------------------------------------------
# UTILS
# ---------------------------------------------------------------------
def normalize_extensions(ext_list):
    normalized = []
    for item in ext_list:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, (list, tuple)):
            for sub in item:
                if isinstance(sub, str):
                    normalized.append(sub)
    return tuple(normalized)

# ---------------------------------------------------------------------
# TOOLS
# ---------------------------------------------------------------------
@mcp.tool
async def scan_design_system(directory_path: str, export_format: str = "json") -> Dict[str, Any]:
    if not os.path.exists(directory_path):
        raise ValueError(f"Директория не существует: {directory_path}")

    try:
        parser = DesignSystemParser()
        parser.supported_extensions = normalize_extensions(parser.supported_extensions)
        components = parser.scan_directory(directory_path)

        result = {
            "summary": {
                "total_components": len(components),
                "scanned_directory": directory_path,
                "supported_extensions": parser.supported_extensions
            },
            "components": [],
            "export_format": export_format
        }

        for c in components:
            result["components"].append({
                "name": c.name,
                "file_path": c.file_path,
                "relative_path": os.path.relpath(c.file_path, directory_path),
                "props_count": len(c.props),
                "is_default_export": c.is_default_export,
                "export_type": c.export_type,
                "props": [{"name": p.name, "type": p.type, "required": p.required, "default": p.default} for p in c.props]
            })

        if export_format == "csv":
            result["csv"] = export_to_csv(result)
        elif export_format == "markdown":
            result["markdown"] = export_to_markdown(result)

        TOOL_CALLS_TOTAL.labels(tool_name="scan_design_system", status="success").inc()
        return result

    except Exception as e:
        TOOL_CALLS_TOTAL.labels(tool_name="scan_design_system", status="error").inc()
        raise ValueError(f"Ошибка при сканировании: {str(e)}")


@mcp.tool
async def find_component_by_name(directory_path: str, component_name: str) -> Dict[str, Any]:
    try:
        parser = DesignSystemParser()
        parser.supported_extensions = normalize_extensions(parser.supported_extensions)
        components = parser.scan_directory(directory_path)

        found = [c for c in components if c.name.lower() == component_name.lower()]

        TOOL_CALLS_TOTAL.labels(tool_name="find_component_by_name", status="success").inc()

        return {
            "found_count": len(found),
            "components": [{"name": c.name, "file_path": c.file_path, "props": [p.name for p in c.props]} for c in found]
        }

    except Exception as e:
        TOOL_CALLS_TOTAL.labels(tool_name="find_component_by_name", status="error").inc()
        raise ValueError(f"Ошибка при поиске компонента: {str(e)}")


def export_to_csv(result: Dict[str, Any]) -> str:
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Component Name", "File Path", "Props Count", "Export Type"])
    for comp in result["components"]:
        writer.writerow([comp["name"], comp["relative_path"], comp["props_count"], comp["export_type"]])
    return output.getvalue()


def export_to_markdown(result: Dict[str, Any]) -> str:
    md_lines = [
        "# Дизайн-система: Анализ компонентов",
        f"**Всего компонентов:** {result['summary']['total_components']}",
        f"**Директория:** {result['summary']['scanned_directory']}",
        "\n## Компоненты\n"
    ]
    for comp in result["components"]:
        md_lines.append(f"### {comp['name']}")
        md_lines.append(f"- **Файл:** `{comp['relative_path']}`")
        md_lines.append(f"- **Тип экспорта:** {comp['export_type']}")
        md_lines.append(f"- **Пропсы ({comp['props_count']}):**")
        for p in comp["props"]:
            required = "✓" if p["required"] else "✗"
            md_lines.append(f"  - `{p['name']}`: {p['type']} (обязательный: {required})")
        md_lines.append("")
    return "\n".join(md_lines)
