"""
Асинхронный клиент для работы с Figma API.
"""
import aiohttp
import asyncio
from typing import Dict, Any, Optional
from .config import config
from .mcp_instance import FIGMA_API_CALLS

class FigmaClient:
    """Клиент для работы с Figma API."""
    
    def __init__(self):
        self.base_url = config.figma.base_url
        self.headers = {
            "X-Figma-Token": config.figma.access_token,
            "Content-Type": "application/json"
        }
        self.timeout = aiohttp.ClientTimeout(total=config.figma.timeout)
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Выполняет HTTP-запрос к Figma API."""
        url = f"{self.base_url}/{endpoint}"
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.request(method, url, headers=self.headers, **kwargs) as response:
                    FIGMA_API_CALLS.labels(
                        endpoint=url.split('/')[-1],
                        status=response.status
                    ).inc()
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise FigmaAPIError(f"Figma API error ({response.status}): {error_text}")
                    
                    return await response.json()
                    
            except asyncio.TimeoutError:
                raise FigmaAPIError("Request timeout to Figma API")
            except aiohttp.ClientError as e:
                raise FigmaAPIError(f"HTTP client error: {str(e)}")
    
    async def get_file(self, file_key: str, node_ids: Optional[str] = None) -> Dict[str, Any]:
        """Получает структуру файла Figma."""
        params = {}
        if node_ids:
            params["ids"] = node_ids
        
        return await self._make_request("GET", f"files/{file_key}", params=params)

class FigmaAPIError(Exception):
    """Ошибка Figma API."""
    pass

figma_client = FigmaClient()