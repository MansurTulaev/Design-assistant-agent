"""
Модуль для работы с NPM Registry API
Получение данных о компонентах из публичных NPM пакетов
"""
import httpx
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import re
from cache_service import CacheService


class NPMRegistryClient:
    """Клиент для работы с NPM Registry API"""
    
    BASE_URL = "https://registry.npmjs.org"
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Инициализация клиента
        
        Args:
            cache_service: Сервис кэширования (опционально)
        """
        self.client = httpx.AsyncClient(
            headers={
                "Accept": "application/json",
                "User-Agent": "MCP-RAG-Server/1.0.0"
            },
            timeout=30.0
        )
        self.cache = cache_service
    
    async def get_package_info(self, package_name: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о пакете из NPM Registry
        
        Args:
            package_name: Название пакета (например, '@mui/material')
            version: Версия пакета (опционально, по умолчанию latest)
        
        Returns:
            Словарь с информацией о пакете или None при ошибке
        """
        # Проверяем кэш
        if self.cache:
            cached = await self.cache.get_package_info(package_name, version)
            if cached:
                return cached
        
        try:
            url = f"{self.BASE_URL}/{package_name}"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            
            result = None
            if version:
                if version in data.get("versions", {}):
                    result = data["versions"][version]
            else:
                # Возвращаем latest версию
                latest_version = data.get("dist-tags", {}).get("latest")
                if latest_version and latest_version in data.get("versions", {}):
                    result = data["versions"][latest_version]
                else:
                    result = data
            
            # Сохраняем в кэш
            if result and self.cache:
                await self.cache.set_package_info(package_name, version, result)
            
            return result
        except httpx.RequestError as e:
            print(f"Ошибка при получении информации о пакете {package_name}: {e}")
            return None
    
    async def get_package_metadata(self, package_name: str) -> Optional[Dict[str, Any]]:
        """
        Получить метаданные пакета (без полной информации о версиях)
        
        Args:
            package_name: Название пакета
        
        Returns:
            Словарь с метаданными пакета
        """
        # Проверяем кэш
        if self.cache:
            cached = await self.cache.get_npm_metadata(package_name)
            if cached:
                return cached
        
        try:
            url = f"{self.BASE_URL}/{package_name}"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            
            metadata = {
                "name": data.get("name"),
                "description": data.get("description"),
                "latest_version": data.get("dist-tags", {}).get("latest"),
                "versions": list(data.get("versions", {}).keys()),
                "keywords": data.get("keywords", []),
                "homepage": data.get("homepage"),
                "repository": data.get("repository"),
                "author": data.get("author"),
                "license": data.get("license"),
                "time": data.get("time", {}),
                "maintainers": data.get("maintainers", []),
            }
            
            # Сохраняем в кэш
            if self.cache:
                await self.cache.set_npm_metadata(package_name, metadata)
            
            return metadata
        except httpx.RequestError as e:
            print(f"Ошибка при получении метаданных пакета {package_name}: {e}")
            return None
    
    async def get_readme(self, package_name: str, version: Optional[str] = None) -> Optional[str]:
        """
        Получить README файл пакета
        
        Args:
            package_name: Название пакета
            version: Версия пакета (опционально)
        
        Returns:
            Содержимое README или None
        """
        package_info = await self.get_package_info(package_name, version)
        if not package_info:
            return None
        
        # README может быть в разных полях
        readme = (
            package_info.get("readme") or 
            package_info.get("readmeFilename") or
            ""
        )
        
        return readme
    
    async def search_packages(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Поиск пакетов в NPM Registry
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных пакетов
        """
        # Проверяем кэш
        if self.cache:
            cached = await self.cache.get_npm_search(query, limit)
            if cached:
                return cached
        
        try:
            url = f"{self.BASE_URL}/-/v1/search"
            params = {
                "text": query,
                "size": limit
            }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for package in data.get("objects", []):
                pkg = package.get("package", {})
                results.append({
                    "name": pkg.get("name"),
                    "description": pkg.get("description"),
                    "version": pkg.get("version"),
                    "keywords": pkg.get("keywords", []),
                    "date": pkg.get("date"),
                    "publisher": pkg.get("publisher", {}).get("username"),
                    "score": package.get("score", {}).get("final", 0)
                })
            
            # Сохраняем в кэш
            if self.cache:
                await self.cache.set_npm_search(query, limit, results)
            
            return results
        except httpx.RequestError as e:
            print(f"Ошибка при поиске пакетов: {e}")
            return []
    
    def extract_components_from_readme(self, readme: str, package_name: str) -> List[Dict[str, Any]]:
        """
        Извлечь информацию о компонентах из README
        
        Args:
            readme: Содержимое README
            package_name: Название пакета
        
        Returns:
            Список найденных компонентов
        """
        components = []
        
        if not readme:
            return components
        
        # Поиск упоминаний компонентов (базовый парсинг)
        # Ищем паттерны типа "## ComponentName", "### ComponentName", "<ComponentName"
        component_patterns = [
            r'##\s+([A-Z][a-zA-Z0-9]+)',  # ## ComponentName
            r'###\s+([A-Z][a-zA-Z0-9]+)',  # ### ComponentName
            r'<([A-Z][a-zA-Z0-9]+)',       # <ComponentName
            r'import\s+\{?\s*([A-Z][a-zA-Z0-9]+)',  # import { ComponentName }
        ]
        
        found_components = set()
        for pattern in component_patterns:
            matches = re.findall(pattern, readme)
            found_components.update(matches)
        
        # Фильтруем известные не-компоненты
        exclude_words = {
            "Installation", "Usage", "Example", "Examples", "API", "Props",
            "Introduction", "Getting", "Started", "Documentation", "License",
            "Contributing", "Changelog", "README", "Table", "Contents"
        }
        
        for component_name in found_components:
            if component_name not in exclude_words and len(component_name) > 2:
                components.append({
                    "name": component_name,
                    "package": package_name,
                    "source": "readme"
                })
        
        return components
    
    async def get_typescript_types(self, package_name: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Получить TypeScript типы из пакета (если доступны)
        
        Args:
            package_name: Название пакета
            version: Версия пакета
        
        Returns:
            Информация о типах или None
        """
        package_info = await self.get_package_info(package_name, version)
        if not package_info:
            return None
        
        # Проверяем наличие types или typings в package.json
        types_info = {
            "types": package_info.get("types"),
            "typings": package_info.get("typings"),
            "main": package_info.get("main"),
            "module": package_info.get("module"),
        }
        
        return types_info if any(types_info.values()) else None
    
    async def get_package_dependencies(self, package_name: str, version: Optional[str] = None) -> Dict[str, str]:
        """
        Получить зависимости пакета
        
        Args:
            package_name: Название пакета
            version: Версия пакета
        
        Returns:
            Словарь зависимостей {package: version}
        """
        package_info = await self.get_package_info(package_name, version)
        if not package_info:
            return {}
        
        deps = {}
        deps.update(package_info.get("dependencies", {}))
        deps.update(package_info.get("peerDependencies", {}))
        deps.update(package_info.get("devDependencies", {}))
        
        return deps
    
    async def format_component_data(self, package_name: str, component_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Форматировать данные компонента в структурированный формат
        
        Args:
            package_name: Название пакета
            component_name: Название компонента (опционально)
        
        Returns:
            Структурированные данные компонента
        """
        package_info = await self.get_package_info(package_name)
        if not package_info:
            return {}
        
        readme = await self.get_readme(package_name)
        components = self.extract_components_from_readme(readme, package_name) if readme else []
        
        dependencies = await self.get_package_dependencies(package_name)
        types = await self.get_typescript_types(package_name)
        
        return {
            "package": {
                "name": package_name,
                "version": package_info.get("version"),
                "description": package_info.get("description"),
                "keywords": package_info.get("keywords", []),
                "homepage": package_info.get("homepage"),
                "repository": package_info.get("repository"),
                "license": package_info.get("license"),
            },
            "components": components,
            "readme_snippet": readme[:500] if readme else None,  # Первые 500 символов
            "dependencies": dependencies,
            "types": types,
        }
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.aclose()

