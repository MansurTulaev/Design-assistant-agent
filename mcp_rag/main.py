from fastmcp import FastMCP
import json
import asyncio
from typing import Optional, List, Dict, Any
import sys
import os

# Добавляем путь к модулям приложения
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from npm_registry import NPMRegistryClient
from rag_service import RAGService
from cache_service import CacheService
from storybook_parser import StorybookParser

mcp = FastMCP(name="mcp_rag", version="1.0.0")

# Инициализация сервиса кэширования
cache_service = CacheService()

# Инициализация клиента NPM Registry с кэшированием
npm_client = NPMRegistryClient(cache_service=cache_service)

# Инициализация RAG сервиса с кэшированием
rag_service = RAGService(cache_service=cache_service)

# Инициализация парсера Storybook с кэшированием
storybook_parser = StorybookParser(cache_service=cache_service)


# Инициализация кэша при старте
async def init_cache():
    """Инициализировать подключение к Redis"""
    await cache_service.connect()


# Запускаем инициализацию кэша
try:
    asyncio.run(init_cache())
except Exception as e:
    print(f"⚠ Не удалось инициализировать кэш: {e}. Работа продолжается без кэширования.")


@mcp.tool
async def search_npm_packages(query: str, limit: int = 20) -> str:
    """
    Поиск пакетов в NPM Registry по ключевым словам
    
    Используйте этот инструмент для поиска пакетов перед использованием get_npm_component_data.
    
    Args:
        query: Поисковый запрос (например, "react button component", "material-ui", "kontur ui button")
        limit: Максимальное количество результатов (по умолчанию 20)
    
    Returns:
        JSON строка с результатами поиска пакетов, включая название пакета (name), которое можно использовать в get_npm_component_data
    
    Пример:
        Для поиска кнопок: search_npm_packages("button react")
        Затем используйте найденное название пакета в get_npm_component_data
    """
    results = await npm_client.search_packages(query, limit)
    return json.dumps({
        "query": query,
        "total": len(results),
        "packages": results
    }, ensure_ascii=False, indent=2)


@mcp.tool
async def get_npm_package_info(package_name: str, version: Optional[str] = None) -> str:
    """
    Получить подробную информацию о NPM пакете
    
    Args:
        package_name: Название пакета (например, "@mui/material", "antd", "@chakra-ui/react")
        version: Версия пакета (опционально, по умолчанию latest)
    
    Returns:
        JSON строка с информацией о пакете
    """
    metadata = await npm_client.get_package_metadata(package_name)
    if not metadata:
        return json.dumps({
            "error": f"Пакет {package_name} не найден или недоступен"
        }, ensure_ascii=False)
    
    package_info = await npm_client.get_package_info(package_name, version)
    
    result = {
        "package": {
            "name": metadata.get("name"),
            "description": metadata.get("description"),
            "version": metadata.get("latest_version") if not version else version,
            "keywords": metadata.get("keywords", []),
            "homepage": metadata.get("homepage"),
            "repository": metadata.get("repository"),
            "author": metadata.get("author"),
            "license": metadata.get("license"),
            "maintainers": metadata.get("maintainers", []),
        },
        "dependencies": await npm_client.get_package_dependencies(package_name, version),
        "types": await npm_client.get_typescript_types(package_name, version),
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


@mcp.tool
async def get_npm_component_data(package_name: str, component_name: Optional[str] = None) -> str:
    """
    Получить данные о компонентах из NPM пакета
    
    Извлекает информацию о компонентах из README и метаданных пакета.
    
    ВАЖНО: Сначала нужно найти пакет через search_npm_packages или search_ui_libraries,
    затем использовать его название здесь.
    
    Args:
        package_name: Название пакета (обязательно, например, "@mui/material", "antd", "@skbkontur/react-ui")
        component_name: Название конкретного компонента для фильтрации (опционально, например, "Button", "Modal")
    
    Returns:
        JSON строка с данными о компонентах
    
    Пример использования:
        1. Сначала найдите пакет: search_ui_libraries("button")
        2. Затем получите компоненты: get_npm_component_data("@mui/material", "Button")
    """
    if not package_name or not package_name.strip():
        return json.dumps({
            "error": "package_name обязателен. Сначала найдите пакет через search_npm_packages или search_ui_libraries"
        }, ensure_ascii=False)
    
    data = await npm_client.format_component_data(package_name, component_name)
    
    if not data:
        return json.dumps({
            "error": f"Не удалось получить данные для пакета {package_name}",
            "suggestion": "Попробуйте сначала найти пакет через search_npm_packages или search_ui_libraries"
        }, ensure_ascii=False)
    
    # Фильтруем по имени компонента, если указано
    if component_name and data.get("components"):
        data["components"] = [
            comp for comp in data["components"]
            if component_name.lower() in comp.get("name", "").lower()
        ]
    
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


@mcp.tool
async def get_npm_readme(package_name: str, version: Optional[str] = None) -> str:
    """
    Получить README файл из NPM пакета
    
    Args:
        package_name: Название пакета
        version: Версия пакета (опционально)
    
    Returns:
        Содержимое README файла
    """
    readme = await npm_client.get_readme(package_name, version)
    
    if not readme:
        return json.dumps({
            "error": f"README не найден для пакета {package_name}",
            "package": package_name,
            "version": version or "latest"
        }, ensure_ascii=False)
    
    return json.dumps({
        "package": package_name,
        "version": version or "latest",
        "readme": readme,
        "length": len(readme)
    }, ensure_ascii=False, indent=2)


@mcp.tool
async def search_ui_libraries(query: str, limit: int = 10) -> str:
    """
    Поиск UI библиотек компонентов в NPM Registry
    
    Специализированный поиск для популярных UI библиотек:
    Material-UI, Ant Design, Chakra UI, Radix UI, Headless UI, Kontur UI и другие.
    
    Используйте этот инструмент для поиска UI библиотек перед использованием get_npm_component_data.
    
    Args:
        query: Поисковый запрос (например, "button", "form", "modal", "ok button")
        limit: Максимальное количество результатов
    
    Returns:
        JSON строка с найденными UI библиотеками и компонентами.
        Каждый результат содержит поле "name" - название пакета, которое можно использовать в get_npm_component_data.
    
    Пример:
        Для поиска кнопок: search_ui_libraries("button")
        Затем используйте найденное название пакета (например, "@mui/material") в get_npm_component_data("@mui/material", "Button")
    """
    # Популярные UI библиотеки для приоритетного поиска
    popular_libraries = [
        "@mui/material", "@mui/base", "antd", "@chakra-ui/react",
        "@radix-ui/react-", "@headlessui/react", "@mantine/core",
        "react-bootstrap", "semantic-ui-react",
        "@skbkontur/react-ui", "@skbkontur/react-icons",  # Kontur UI
        "kontur-ui"  # Альтернативное название
    ]
    
    # Поиск пакетов
    search_results = await npm_client.search_packages(query, limit * 2)
    
    # Фильтруем и приоритизируем UI библиотеки
    ui_packages = []
    other_packages = []
    
    for pkg in search_results:
        name = pkg.get("name", "").lower()
        is_ui_library = any(
            lib.lower() in name for lib in popular_libraries
        ) or any(
            keyword in pkg.get("keywords", []) 
            for keyword in ["react", "ui", "component", "design-system"]
        )
        
        if is_ui_library:
            ui_packages.append(pkg)
        else:
            other_packages.append(pkg)
    
    # Объединяем результаты (UI библиотеки сначала)
    results = ui_packages[:limit] + other_packages[:limit - len(ui_packages)]
    
    return json.dumps({
        "query": query,
        "total": len(results),
        "ui_libraries": results,
        "popular_libraries_searched": popular_libraries
    }, ensure_ascii=False, indent=2, default=str)


@mcp.tool
async def index_npm_package_to_rag(package_name: str) -> str:
    """
    Индексировать компоненты из NPM пакета в RAG (векторную БД)
    
    Получает данные о компонентах из пакета и сохраняет их в Qdrant
    для последующего семантического поиска
    
    Args:
        package_name: Название пакета (например, "@mui/material", "antd")
    
    Returns:
        JSON строка с результатами индексации
    """
    try:
        # Получаем данные о компонентах
        component_data = await npm_client.format_component_data(package_name)
        
        if not component_data:
            return json.dumps({
                "error": f"Не удалось получить данные для пакета {package_name}",
                "package": package_name
            }, ensure_ascii=False)
        
        # Индексируем компоненты
        indexed_ids = await rag_service.index_package_components(component_data)
        
        return json.dumps({
            "package": package_name,
            "indexed_components": len(indexed_ids),
            "component_ids": indexed_ids,
            "status": "success"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "package": package_name,
            "status": "error"
        }, ensure_ascii=False)


@mcp.tool
async def search_components_rag(query: str, limit: int = 10, category: Optional[str] = None, package: Optional[str] = None) -> str:
    """
    Семантический поиск компонентов в RAG (векторная БД)
    
    Выполняет семантический поиск по индексированным компонентам
    используя векторные эмбеддинги
    
    Args:
        query: Поисковый запрос (например, "button with icon", "form input validation")
        limit: Максимальное количество результатов (по умолчанию 10)
        category: Фильтр по категории (atoms, molecules, organisms, templates, pages)
        package: Фильтр по названию пакета (например, "@mui/material")
    
    Returns:
        JSON строка с результатами поиска и релевантностью
    """
    try:
        filters = {}
        if category:
            filters["category"] = category
        if package:
            filters["package"] = package
        
        results = await rag_service.search(query, limit, filters if filters else None)
        
        return json.dumps({
            "query": query,
            "total": len(results),
            "results": results,
            "filters": filters if filters else None
        }, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "query": query
        }, ensure_ascii=False)


@mcp.tool
async def get_rag_collection_stats() -> str:
    """
    Получить статистику коллекции в RAG
    
    Возвращает информацию о количестве индексированных компонентов
    
    Returns:
        JSON строка со статистикой коллекции
    """
    try:
        stats = await rag_service.get_collection_stats()
        return json.dumps(stats, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return json.dumps({
            "error": str(e)
        }, ensure_ascii=False)


@mcp.tool
async def parse_storybook_url(storybook_url: str) -> str:
    """
    Парсинг компонентов из Storybook URL
    
    Извлекает информацию о компонентах из Storybook по указанному URL.
    Поддерживает различные версии Storybook и извлекает метаданные компонентов.
    
    Args:
        storybook_url: URL Storybook (например, "https://storybook.example.com" или "https://storybook.skbkontur.ru")
    
    Returns:
        JSON строка с информацией о компонентах из Storybook
    """
    try:
        result = await storybook_parser.parse_storybook_url(storybook_url)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "url": storybook_url
        }, ensure_ascii=False)


@mcp.tool
async def index_storybook_to_rag(storybook_url: str, package_name: Optional[str] = None) -> str:
    """
    Индексировать компоненты из Storybook в RAG (векторную БД)
    
    Парсит компоненты из Storybook и сохраняет их в Qdrant
    для последующего семантического поиска
    
    Args:
        storybook_url: URL Storybook
        package_name: Название пакета (опционально, для связи с NPM пакетом)
    
    Returns:
        JSON строка с результатами индексации
    """
    try:
        # Парсим Storybook
        storybook_data = await storybook_parser.parse_storybook_url(storybook_url)
        
        if "error" in storybook_data:
            return json.dumps(storybook_data, ensure_ascii=False, indent=2)
        
        # Преобразуем компоненты в формат для RAG
        indexed_ids = []
        components = storybook_data.get("components", [])
        
        for component in components:
            # Формируем данные компонента в формате DesignComponent
            component_data = {
                "id": component.get("id", component.get("name", "")),
                "name": component.get("name", ""),
                "description": component.get("description", ""),
                "category": component.get("category", component.get("kind", "components")),
                "type": "component",
                "package": {
                    "name": package_name or storybook_data.get("metadata", {}).get("title", "storybook"),
                    "version": storybook_data.get("metadata", {}).get("storybook_version", "unknown"),
                    "source": "storybook"
                },
                "source_url": component.get("url", storybook_url),
                "code_snippet": component.get("code_snippet", ""),
                "tags": ["storybook", component.get("category", ""), component.get("source", "")]
            }
            
            # Индексируем компонент
            point_id = await rag_service.index_component(component_data)
            indexed_ids.append(point_id)
        
        return json.dumps({
            "url": storybook_url,
            "package": package_name,
            "indexed_components": len(indexed_ids),
            "component_ids": indexed_ids,
            "status": "success"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "url": storybook_url,
            "status": "error"
        }, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()