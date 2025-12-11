"""
Сервис кэширования с использованием Redis
Кэширует метаданные NPM, результаты поиска и эмбеддинги
"""
import os
import json
import hashlib
from typing import Optional, Any, Dict, List
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
from datetime import timedelta


class CacheService:
    """Сервис для кэширования данных в Redis"""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        redis_db: int = 0,
        default_ttl: int = 3600  # 1 час по умолчанию
    ):
        """
        Инициализация сервиса кэширования
        
        Args:
            redis_url: Полный URL Redis (redis://host:port)
            redis_host: Хост Redis (по умолчанию redis или localhost)
            redis_port: Порт Redis (по умолчанию 6379)
            redis_db: Номер базы данных Redis
            default_ttl: Время жизни кэша по умолчанию (в секундах)
        """
        # Определяем параметры подключения
        if redis_url:
            self.redis_url = redis_url
        else:
            # В Docker используем имя сервиса, локально - localhost
            host = redis_host or os.getenv("REDIS_HOST", "redis" if os.getenv("DOCKER_ENV") else "localhost")
            port = redis_port or int(os.getenv("REDIS_PORT", "6379"))
            self.redis_url = f"redis://{host}:{port}"
        
        self.redis_db = redis_db
        self.default_ttl = default_ttl
        self.client: Optional[Any] = None
        self._enabled = (
            os.getenv("REDIS_CACHE_ENABLED", "true").lower() == "true" 
            and REDIS_AVAILABLE
        )
    
    async def connect(self):
        """Подключиться к Redis"""
        if not self._enabled or not REDIS_AVAILABLE:
            if not REDIS_AVAILABLE:
                print("⚠ Redis не установлен. Кэширование отключено.")
            return
        
        try:
            self.client = await redis.from_url(
                self.redis_url,
                db=self.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Проверяем подключение
            await self.client.ping()
            print("✓ Подключение к Redis установлено")
        except Exception as e:
            print(f"⚠ Не удалось подключиться к Redis: {e}. Кэширование отключено.")
            self._enabled = False
            self.client = None
    
    async def disconnect(self):
        """Отключиться от Redis"""
        if self.client:
            await self.client.close()
            self.client = None
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Создать ключ кэша из префикса и параметров
        
        Args:
            prefix: Префикс ключа (например, "npm:metadata")
            *args: Позиционные аргументы для ключа
            **kwargs: Именованные аргументы для ключа
        
        Returns:
            Строка ключа
        """
        # Создаем строку из всех параметров
        key_parts = [prefix]
        key_parts.extend(str(arg) for arg in args)
        if kwargs:
            # Сортируем kwargs для консистентности
            sorted_kwargs = sorted(kwargs.items())
            key_parts.extend(f"{k}:{v}" for k, v in sorted_kwargs)
        
        key_string = ":".join(key_parts)
        
        # Если ключ слишком длинный, используем хэш
        if len(key_string) > 200:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{prefix}:hash:{key_hash}"
        
        return key_string
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Получить значение из кэша
        
        Args:
            key: Ключ кэша
        
        Returns:
            Значение или None, если не найдено
        """
        if not self._enabled or not self.client:
            return None
        
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Ошибка при чтении из кэша: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ):
        """
        Сохранить значение в кэш
        
        Args:
            key: Ключ кэша
            value: Значение для сохранения
            ttl: Время жизни в секундах (по умолчанию default_ttl)
        """
        if not self._enabled or not self.client:
            return
        
        try:
            json_value = json.dumps(value, ensure_ascii=False, default=str)
            ttl = ttl or self.default_ttl
            await self.client.setex(key, ttl, json_value)
        except Exception as e:
            print(f"Ошибка при записи в кэш: {e}")
    
    async def delete(self, key: str):
        """Удалить ключ из кэша"""
        if not self._enabled or not self.client:
            return
        
        try:
            await self.client.delete(key)
        except Exception as e:
            print(f"Ошибка при удалении из кэша: {e}")
    
    async def clear_pattern(self, pattern: str):
        """Удалить все ключи по паттерну"""
        if not self._enabled or not self.client:
            return
        
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self.client.delete(*keys)
        except Exception as e:
            print(f"Ошибка при очистке кэша по паттерну: {e}")
    
    # Специализированные методы для разных типов данных
    
    async def get_npm_metadata(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Получить метаданные NPM пакета из кэша"""
        key = self._make_key("npm:metadata", package_name)
        return await self.get(key)
    
    async def set_npm_metadata(
        self,
        package_name: str,
        metadata: Dict[str, Any],
        ttl: int = 86400  # 24 часа для метаданных
    ):
        """Сохранить метаданные NPM пакета в кэш"""
        key = self._make_key("npm:metadata", package_name)
        await self.set(key, metadata, ttl)
    
    async def get_npm_search(self, query: str, limit: int) -> Optional[List[Dict[str, Any]]]:
        """Получить результаты поиска NPM из кэша"""
        key = self._make_key("npm:search", query, limit=limit)
        return await self.get(key)
    
    async def set_npm_search(
        self,
        query: str,
        limit: int,
        results: List[Dict[str, Any]],
        ttl: int = 3600  # 1 час для результатов поиска
    ):
        """Сохранить результаты поиска NPM в кэш"""
        key = self._make_key("npm:search", query, limit=limit)
        await self.set(key, results, ttl)
    
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Получить эмбеддинг из кэша"""
        key = self._make_key("embedding", hashlib.md5(text.encode()).hexdigest())
        return await self.get(key)
    
    async def set_embedding(
        self,
        text: str,
        embedding: List[float],
        ttl: int = 604800  # 7 дней для эмбеддингов (они не меняются)
    ):
        """Сохранить эмбеддинг в кэш"""
        key = self._make_key("embedding", hashlib.md5(text.encode()).hexdigest())
        await self.set(key, embedding, ttl)
    
    async def get_package_info(
        self,
        package_name: str,
        version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Получить информацию о пакете из кэша"""
        key = self._make_key("npm:package", package_name, version=version or "latest")
        return await self.get(key)
    
    async def set_package_info(
        self,
        package_name: str,
        version: Optional[str],
        package_info: Dict[str, Any],
        ttl: int = 86400  # 24 часа
    ):
        """Сохранить информацию о пакете в кэш"""
        key = self._make_key("npm:package", package_name, version=version or "latest")
        await self.set(key, package_info, ttl)

