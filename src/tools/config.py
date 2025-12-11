"""Конфигурационные параметры для Figma MCP сервера."""
import os
import logging
from typing import Dict, Any

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("mcp_figma")

# Figma API Configuration
FIGMA_ACCESS_TOKEN = os.getenv("FIGMA_ACCESS_TOKEN", "figd_LQnLwvow3ffJ9FLOsiG6bUDvLQ1xq2xcR-BZ3ANr")
KONTUR_UI_FILE_ID = os.getenv("KONTUR_UI_FILE_ID", "KQc2jUV5CuCDqZ7hHTX0vc")
TEST_FILE_ID = os.getenv("TEST_FILE_ID", "d4qp6XOTZc3abUbq5UUDe7")

# Server Configuration
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")

# Performance Configuration
FIGMA_API_TIMEOUT = int(os.getenv("FIGMA_API_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "50000000"))  # 50 MB
MAX_COMPONENTS = int(os.getenv("MAX_COMPONENTS", "1000"))

# Mapping Configuration
MIN_CONFIDENCE_THRESHOLD = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "60.0"))
MAX_TREE_DEPTH = int(os.getenv("MAX_TREE_DEPTH", "5"))

# Cache Configuration (в секундах)
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 минут
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"

# OpenTelemetry Configuration
OTEL_ENDPOINT = os.getenv("OTEL_ENDPOINT", "")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "mcp-figma-scanner")

# Validation Configuration
ALLOWED_FILE_KEYS = [
    KONTUR_UI_FILE_ID,
    TEST_FILE_ID
    # Можно добавить другие разрешенные ключи файлов
]

# Kontur UI Component Knowledge Base
KONTUR_UI_COMPONENTS = {
    "button": {
        "import_path": "@skbkontur/react-ui/Button",
        "props": ["variant", "size", "disabled", "loading", "onClick"],
        "variants": ["primary", "secondary", "danger", "link"],
        "sizes": ["small", "medium", "large"]
    },
    "input": {
        "import_path": "@skbkontur/react-ui/Input",
        "props": ["value", "onChange", "placeholder", "disabled", "error", "warning", "size"],
        "types": ["text", "password", "email", "number"],
        "sizes": ["small", "medium", "large"]
    },
    "textarea": {
        "import_path": "@skbkontur/react-ui/Textarea",
        "props": ["value", "onChange", "placeholder", "disabled", "resize", "rows", "maxRows"]
    },
    "select": {
        "import_path": "@skbkontur/react-ui/Select",
        "props": ["value", "onChange", "items", "placeholder", "disabled", "search", "allowClear"]
    },
    "checkbox": {
        "import_path": "@skbkontur/react-ui/Checkbox",
        "props": ["checked", "onChange", "disabled", "indeterminate", "label"]
    },
    "radio": {
        "import_path": "@skbkontur/react-ui/Radio",
        "props": ["checked", "onChange", "disabled", "value", "label"]
    },
    "switch": {
        "import_path": "@skbkontur/react-ui/Switch",
        "props": ["checked", "onChange", "disabled", "loading"]
    },
    "modal": {
        "import_path": "@skbkontur/react-ui/Modal",
        "props": ["show", "onClose", "width", "height", "title", "footerButtons"]
    },
    "card": {
        "import_path": "@skbkontur/react-ui/Card",
        "props": ["children", "hover", "padding", "margin", "border"]
    },
    "table": {
        "import_path": "@skbkontur/react-ui/Table",
        "props": ["data", "columns", "rowKey", "loading", "pagination"]
    },
    "dropdown": {
        "import_path": "@skbkontur/react-ui/Dropdown",
        "props": ["caption", "menu", "disabled", "open", "onOpenChange"]
    },
    "tooltip": {
        "import_path": "@skbkontur/react-ui/Tooltip",
        "props": ["render", "children", "pos", "trigger", "disable"]
    },
    "tabs": {
        "import_path": "@skbkontur/react-ui/Tabs",
        "props": ["value", "onChange", "vertical", "items"]
    },
    "accordion": {
        "import_path": "@skbkontur/react-ui/Accordion",
        "props": ["multiple", "items", "expanded", "onChange"]
    },
    "badge": {
        "import_path": "@skbkontur/react-ui/Badge",
        "props": ["count", "dot", "status", "text", "overflowCount"]
    },
    "avatar": {
        "import_path": "@skbkontur/react-ui/Avatar",
        "props": ["src", "size", "shape", "icon", "children"]
    },
    "icon": {
        "import_path": "@skbkontur/react-ui/Icon",
        "props": ["name", "size", "color", "spin", "rotate"]
    },
    "spinner": {
        "import_path": "@skbkontur/react-ui/Spinner",
        "props": ["type", "size", "caption", "dimmed"]
    },
    "progress": {
        "import_path": "@skbkontur/react-ui/Progress",
        "props": ["percent", "status", "strokeWidth", "showInfo", "format"]
    },
    "skeleton": {
        "import_path": "@skbkontur/react-ui/Skeleton",
        "props": ["active", "avatar", "title", "paragraph", "loading"]
    },
    "alert": {
        "import_path": "@skbkontur/react-ui/Alert",
        "props": ["type", "children", "close", "onClose", "header"]
    },
    "notification": {
        "import_path": "@skbkontur/react-ui/Notification",
        "props": ["type", "title", "children", "delay", "onClose"]
    },
    "breadcrumbs": {
        "import_path": "@skbkontur/react-ui/Breadcrumbs",
        "props": ["items", "separator", "maxCount", "overflowedIndicator"]
    },
    "pagination": {
        "import_path": "@skbkontur/react-ui/Pagination",
        "props": ["current", "total", "pageSize", "onChange", "showSizeChanger"]
    },
    "stepper": {
        "import_path": "@skbkontur/react-ui/Stepper",
        "props": ["activeStep", "steps", "orientation", "alternativeLabel"]
    },
    "rating": {
        "import_path": "@skbkontur/react-ui/Rating",
        "props": ["value", "onChange", "count", "size", "disabled", "allowHalf"]
    },
    "slider": {
        "import_path": "@skbkontur/react-ui/Slider",
        "props": ["value", "onChange", "min", "max", "step", "marks", "disabled"]
    },
    "datepicker": {
        "import_path": "@skbkontur/react-ui/DatePicker",
        "props": ["value", "onChange", "format", "disabled", "allowClear", "showToday"]
    },
    "timepicker": {
        "import_path": "@skbkontur/react-ui/TimePicker",
        "props": ["value", "onChange", "format", "disabled", "allowClear", "hourStep", "minuteStep"]
    },
    "calendar": {
        "import_path": "@skbkontur/react-ui/Calendar",
        "props": ["value", "onChange", "mode", "validRange", "disabledDate"]
    },
    "tree": {
        "import_path": "@skbkontur/react-ui/Tree",
        "props": ["data", "defaultExpandAll", "defaultExpandedKeys", "onSelect", "checkable"]
    },
    "menu": {
        "import_path": "@skbkontur/react-ui/Menu",
        "props": ["mode", "selectedKeys", "onSelect", "items", "theme"]
    },
    "navbar": {
        "import_path": "@skbkontur/react-ui/Navbar",
        "props": ["brand", "children", "fixed", "theme"]
    },
    "sidebar": {
        "import_path": "@skbkontur/react-ui/Sidebar",
        "props": ["collapsed", "onCollapse", "width", "collapsedWidth", "theme"]
    },
    "footer": {
        "import_path": "@skbkontur/react-ui/Footer",
        "props": ["children", "fixed", "theme"]
    },
    "layout": {
        "import_path": "@skbkontur/react-ui/Layout",
        "props": ["children", "hasSider", "style"]
    },
    "grid": {
        "import_path": "@skbkontur/react-ui/Grid",
        "props": ["container", "item", "xs", "sm", "md", "lg", "xl", "spacing", "justify", "alignItems"]
    },
    "flex": {
        "import_path": "@skbkontur/react-ui/Flex",
        "props": ["direction", "wrap", "justify", "align", "gap", "children"]
    },
    "stack": {
        "import_path": "@skbkontur/react-ui/Stack",
        "props": ["direction", "spacing", "divider", "children"]
    },
    "container": {
        "import_path": "@skbkontur/react-ui/Container",
        "props": ["maxWidth", "fixed", "disableGutters", "children"]
    },
    "paper": {
        "import_path": "@skbkontur/react-ui/Paper",
        "props": ["elevation", "square", "variant", "children"]
    },
    "box": {
        "import_path": "@skbkontur/react-ui/Box",
        "props": ["component", "sx", "children"]
    },
    "form": {
        "import_path": "@skbkontur/react-ui/Form",
        "props": ["layout", "colon", "labelAlign", "wrapperCol", "labelCol", "children"]
    },
    "formgroup": {
        "import_path": "@skbkontur/react-ui/FormGroup",
        "props": ["row", "children"]
    },
    "formcontrol": {
        "import_path": "@skbkontur/react-ui/FormControl",
        "props": ["disabled", "error", "fullWidth", "margin", "required", "variant", "children"]
    },
    "formlabel": {
        "import_path": "@skbkontur/react-ui/FormLabel",
        "props": ["children", "htmlFor", "required"]
    },
    "formhelpertext": {
        "import_path": "@skbkontur/react-ui/FormHelperText",
        "props": ["children", "disabled", "error", "filled", "focused", "margin", "required", "variant"]
    },
    "formerrormessage": {
        "import_path": "@skbkontur/react-ui/FormErrorMessage",
        "props": ["children", "show", "icon"]
    }
}

# Component name mappings (alternative names)
COMPONENT_NAME_MAPPINGS = {
    "textfield": "input",
    "text area": "textarea",
    "dropdown menu": "dropdown",
    "select box": "select",
    "check box": "checkbox",
    "radio button": "radio",
    "toggle": "switch",
    "dialog": "modal",
    "popup": "modal",
    "panel": "card",
    "container": "box",
    "wrapper": "box",
    "div": "box",
    "header": "navbar",
    "navigation": "navbar",
    "nav": "navbar",
    "sidebar menu": "sidebar",
    "side panel": "sidebar",
    "foot": "footer",
    "bottom bar": "footer",
    "main layout": "layout",
    "page layout": "layout",
    "flexbox": "flex",
    "flex container": "flex",
    "grid layout": "grid",
    "data table": "table",
    "list": "menu",
    "navigation menu": "menu",
    "steps": "stepper",
    "wizard": "stepper",
    "progress bar": "progress",
    "loading": "spinner",
    "loader": "spinner",
    "icon button": "button",
    "action button": "button",
    "cta button": "button",
    "call to action": "button",
    "link button": "button",
    "ghost button": "button",
    "outline button": "button",
    "filled button": "button",
    "solid button": "button",
    "primary button": "button",
    "secondary button": "button",
    "danger button": "button",
    "warning button": "button",
    "success button": "button",
    "info button": "button"
}

def get_component_info(component_name: str) -> Dict[str, Any]:
    """Получение информации о компоненте Kontur UI по имени."""
    # Нормализуем имя
    normalized_name = component_name.lower().strip()
    
    # Проверяем маппинг альтернативных имен
    if normalized_name in COMPONENT_NAME_MAPPINGS:
        normalized_name = COMPONENT_NAME_MAPPINGS[normalized_name]
    
    # Ищем точное совпадение
    if normalized_name in KONTUR_UI_COMPONENTS:
        return KONTUR_UI_COMPONENTS[normalized_name]
    
    # Ищем частичное совпадение
    for key, info in KONTUR_UI_COMPONENTS.items():
        if key in normalized_name or normalized_name in key:
            return info
    
    # Если не нашли, возвращаем базовую информацию
    return {
        "import_path": f"@skbkontur/react-ui/{component_name}",
        "props": [],
        "variants": [],
        "sizes": []
    }