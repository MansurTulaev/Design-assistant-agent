"""Модуль для работы с Figma API."""
import httpx
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from metrics import logger, FIGMA_API_CALLS_TOTAL

class FigmaAPI:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.figma.com/v1"
        self.headers = {
            "X-Figma-Token": access_token,
            "Content-Type": "application/json"
        }
        self.timeout = 30.0
    
    async def get_file(self, file_key: str) -> Dict[str, Any]:
        """Получение информации о файле Figma."""
        try:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_file", status="started").inc()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/files/{file_key}",
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                FIGMA_API_CALLS_TOTAL.labels(endpoint="get_file", status="success").inc()
                return data
        except httpx.HTTPStatusError as e:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_file", status="error").inc()
            logger.error(f"HTTP error getting file {file_key}: {e}")
            raise
        except Exception as e:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_file", status="error").inc()
            logger.error(f"Error getting file {file_key}: {e}")
            raise
    
    async def get_file_nodes(self, file_key: str, node_ids: List[str]) -> Dict[str, Any]:
        """Получение конкретных нод из файла Figma."""
        try:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_file_nodes", status="started").inc()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/files/{file_key}/nodes",
                    headers=self.headers,
                    params={"ids": ",".join(node_ids)}
                )
                response.raise_for_status()
                data = response.json()
                FIGMA_API_CALLS_TOTAL.labels(endpoint="get_file_nodes", status="success").inc()
                return data
        except httpx.HTTPStatusError as e:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_file_nodes", status="error").inc()
            logger.error(f"HTTP error getting nodes: {e}")
            raise
        except Exception as e:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_file_nodes", status="error").inc()
            logger.error(f"Error getting nodes: {e}")
            raise
    
    async def get_component_sets(self, file_key: str) -> Dict[str, Any]:
        """Получение всех компонентов и component sets из файла."""
        try:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_component_sets", status="started").inc()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/files/{file_key}/component_sets",
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                FIGMA_API_CALLS_TOTAL.labels(endpoint="get_component_sets", status="success").inc()
                return data
        except httpx.HTTPStatusError as e:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_component_sets", status="error").inc()
            logger.error(f"HTTP error getting component sets: {e}")
            raise
        except Exception as e:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_component_sets", status="error").inc()
            logger.error(f"Error getting component sets: {e}")
            raise
    
    async def get_components(self, file_key: str) -> Dict[str, Any]:
        """Получение всех компонентов из файла."""
        try:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_components", status="started").inc()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/files/{file_key}/components",
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                FIGMA_API_CALLS_TOTAL.labels(endpoint="get_components", status="success").inc()
                return data
        except httpx.HTTPStatusError as e:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_components", status="error").inc()
            logger.error(f"HTTP error getting components: {e}")
            raise
        except Exception as e:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_components", status="error").inc()
            logger.error(f"Error getting components: {e}")
            raise
    
    async def get_styles(self, file_key: str) -> Dict[str, Any]:
        """Получение всех стилей из файла."""
        try:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_styles", status="started").inc()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/files/{file_key}/styles",
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                FIGMA_API_CALLS_TOTAL.labels(endpoint="get_styles", status="success").inc()
                return data
        except httpx.HTTPStatusError as e:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_styles", status="error").inc()
            logger.error(f"HTTP error getting styles: {e}")
            raise
        except Exception as e:
            FIGMA_API_CALLS_TOTAL.labels(endpoint="get_styles", status="error").inc()
            logger.error(f"Error getting styles: {e}")
            raise

# Глобальный экземпляр Figma API (будет инициализирован с токеном из env)
figma_api: Optional[FigmaAPI] = None

def init_figma_api(access_token: str):
    """Инициализация Figma API с токеном."""
    global figma_api
    figma_api = FigmaAPI(access_token)
    return figma_api