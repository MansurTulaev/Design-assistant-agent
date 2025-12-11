"""
Модуль для работы с RAG (Retrieval-Augmented Generation)
Интеграция с Qdrant для векторного поиска данных компонентов
"""
import os
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
)
import httpx
from cache_service import CacheService

# Попытка импортировать локальные модели эмбеддингов
try:
    from sentence_transformers import SentenceTransformer
    LOCAL_EMBEDDINGS_AVAILABLE = True
except ImportError:
    LOCAL_EMBEDDINGS_AVAILABLE = False
    SentenceTransformer = None


class RAGService:
    """
    Сервис для работы с RAG через Qdrant
    Сохраняет данные компонентов в векторную БД и выполняет семантический поиск
    """
    
    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        embedding_api_url: Optional[str] = None,
        embedding_api_key: Optional[str] = None,
        embedding_model: Optional[str] = None,
        cache_service: Optional[CacheService] = None
    ):
        """
        Инициализация RAG сервиса
        
        Args:
            qdrant_url: URL Qdrant сервера (по умолчанию http://qdrant:6333)
            qdrant_api_key: API ключ для Qdrant (опционально)
            embedding_api_url: URL API для получения эмбеддингов
            embedding_api_key: API ключ для эмбеддингов
            embedding_model: Модель для эмбеддингов
            cache_service: Сервис кэширования (опционально)
        """
        self.cache = cache_service
        # Настройки Qdrant
        # В Docker используем имя сервиса, локально - localhost
        default_qdrant_url = "http://qdrant:6333" if os.getenv("DOCKER_ENV") else "http://localhost:6333"
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", default_qdrant_url)
        self.qdrant_api_key = qdrant_api_key or os.getenv("QDRANT_API_KEY")
        
        # Настройки эмбеддингов
        self.embedding_api_url = embedding_api_url or os.getenv("RAG_API_URL")
        self.embedding_api_key = embedding_api_key or os.getenv("RAG_API_KEY")
        self.embedding_model = embedding_model or os.getenv("RAG_API_MODEL", "text-embedding-ada-002")
        
        # Локальная модель эмбеддингов (если доступна)
        self.local_embedding_model = None
        self.use_local_embeddings = os.getenv("USE_LOCAL_EMBEDDINGS", "false").lower() == "true"
        
        # Инициализация локальной модели, если нужно
        if self.use_local_embeddings and LOCAL_EMBEDDINGS_AVAILABLE:
            try:
                # Используем легкую модель для быстрой работы
                model_name = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
                print(f"Загрузка локальной модели эмбеддингов: {model_name}")
                self.local_embedding_model = SentenceTransformer(model_name)
                print("✓ Локальная модель загружена")
            except Exception as e:
                print(f"⚠ Ошибка загрузки локальной модели: {e}")
                self.use_local_embeddings = False
        
        # Инициализация клиента Qdrant (async будет использоваться через AsyncQdrantClient)
        self.client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key,
        )
        
        # HTTP клиент для API запросов
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Название коллекции
        self.collection_name = "design_components"
        
        # Размерность векторов
        # Для локальных моделей: all-MiniLM-L6-v2 = 384, all-mpnet-base-v2 = 768
        # Для OpenAI: text-embedding-ada-002 = 1536
        if self.use_local_embeddings and self.local_embedding_model:
            # Получаем размерность из модели
            self.vector_size = self.local_embedding_model.get_sentence_embedding_dimension()
        else:
            # По умолчанию для OpenAI
            self.vector_size = int(os.getenv("VECTOR_SIZE", "1536"))
        
        # Инициализация коллекции
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Создать коллекцию в Qdrant, если её нет"""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"Создана коллекция {self.collection_name}")
        except Exception as e:
            print(f"Ошибка при создании коллекции: {e}")
    
    async def _get_embedding(self, text: str) -> List[float]:
        """
        Получить векторное представление текста (эмбеддинг)
        
        Использует локальную модель, если доступна, иначе API
        Проверяет кэш перед вычислением
        
        Args:
            text: Текст для векторизации
        
        Returns:
            Список чисел (вектор эмбеддинга)
        """
        # Проверяем кэш
        if self.cache:
            cached = await self.cache.get_embedding(text)
            if cached:
                return cached
        
        # Приоритет: локальная модель > API
        embedding = None
        if self.use_local_embeddings and self.local_embedding_model:
            try:
                # Используем локальную модель (быстро и бесплатно)
                embedding = self.local_embedding_model.encode(text, convert_to_numpy=True)
                embedding = embedding.tolist()
            except Exception as e:
                print(f"Ошибка при использовании локальной модели: {e}")
                # Fallback на API, если локальная модель не работает
                if not self.embedding_api_url:
                    raise ValueError("Локальная модель не работает и API не настроен")
        
        # Использование API (OpenAI, Ollama или другой)
        if embedding is None:
            if not self.embedding_api_url:
                raise ValueError(
                    "Не настроен API для эмбеддингов. "
                    "Установите RAG_API_URL или USE_LOCAL_EMBEDDINGS=true"
                )
            
            try:
                # OpenAI API и совместимые форматы
                headers = {}
                if self.embedding_api_key:
                    headers["Authorization"] = f"Bearer {self.embedding_api_key}"
                headers["Content-Type"] = "application/json"
                
                data = {
                    "input": text,
                    "model": self.embedding_model
                }
                
                response = await self.http_client.post(
                    f"{self.embedding_api_url}/embeddings",
                    headers=headers,
                    json=data
                )
                response.raise_for_status()
                result = response.json()
                
                # Поддержка разных форматов ответа
                if "data" in result and len(result["data"]) > 0:
                    embedding = result["data"][0]["embedding"]
                elif "embedding" in result:
                    embedding = result["embedding"]
                else:
                    raise ValueError(f"Неожиданный формат ответа API: {result}")
                        
            except Exception as e:
                print(f"Ошибка при получении эмбеддинга через API: {e}")
                raise
        
        # Сохраняем в кэш
        if embedding and self.cache:
            await self.cache.set_embedding(text, embedding)
        
        return embedding
    
    def _prepare_component_text(self, component_data: Dict[str, Any]) -> str:
        """
        Подготовить текст из данных компонента для векторизации
        
        Args:
            component_data: Данные компонента
        
        Returns:
            Текст для векторизации
        """
        parts = []
        
        # Название и описание
        if component_data.get("name"):
            parts.append(f"Component: {component_data['name']}")
        if component_data.get("description"):
            parts.append(component_data["description"])
        
        # Пакет
        if component_data.get("package"):
            pkg = component_data["package"]
            if pkg.get("name"):
                parts.append(f"Package: {pkg['name']}")
            if pkg.get("description"):
                parts.append(pkg["description"])
            if pkg.get("keywords"):
                parts.append(f"Keywords: {', '.join(pkg['keywords'])}")
        
        # Пропсы
        if component_data.get("props"):
            props_text = "Props: " + ", ".join([
                f"{prop.get('name')} ({prop.get('type')})" 
                for prop in component_data["props"]
            ])
            parts.append(props_text)
        
        # Примеры
        if component_data.get("examples"):
            parts.append("Examples: " + " ".join(component_data["examples"][:3]))
        
        # README snippet
        if component_data.get("readme_snippet"):
            parts.append(component_data["readme_snippet"][:500])
        
        return " ".join(parts)
    
    async def index_component(self, component_data: Dict[str, Any]) -> str:
        """
        Индексировать компонент в векторной БД
        
        Args:
            component_data: Данные компонента в формате схемы DesignComponent
        
        Returns:
            ID точки в Qdrant
        """
        # Генерируем уникальный ID
        point_id = str(uuid.uuid4())
        
        # Подготавливаем текст для векторизации
        text = self._prepare_component_text(component_data)
        
        # Получаем эмбеддинг
        vector = await self._get_embedding(text)
        
        # Подготавливаем метаданные
        payload = {
            "id": component_data.get("id", point_id),
            "name": component_data.get("name", ""),
            "category": component_data.get("category", ""),
            "type": "component",
            "package": component_data.get("package", {}).get("name", ""),
            "source": "npm",
            "data": component_data,  # Полные данные компонента
            "indexed_at": datetime.now().isoformat(),
            "text": text  # Сохраняем исходный текст для отладки
        }
        
        # Добавляем теги
        if component_data.get("tags"):
            payload["tags"] = component_data["tags"]
        elif component_data.get("package", {}).get("keywords"):
            payload["tags"] = component_data["package"]["keywords"]
        
        # Создаем точку
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload=payload
        )
        
        # Сохраняем в Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        return point_id
    
    async def index_package_components(self, package_data: Dict[str, Any]) -> List[str]:
        """
        Индексировать все компоненты из пакета
        
        Args:
            package_data: Данные пакета с компонентами
        
        Returns:
            Список ID индексированных компонентов
        """
        indexed_ids = []
        
        # Индексируем каждый компонент
        components = package_data.get("components", [])
        for component in components:
            component_data = {
                "id": f"{package_data['package']['name']}:{component['name']}",
                "name": component["name"],
                "category": self._infer_category(component["name"]),
                "package": package_data["package"],
                "readme_snippet": package_data.get("readme_snippet"),
                "tags": package_data["package"].get("keywords", []),
            }
            
            try:
                point_id = await self.index_component(component_data)
                indexed_ids.append(point_id)
            except Exception as e:
                print(f"Ошибка при индексации компонента {component['name']}: {e}")
        
        return indexed_ids
    
    def _infer_category(self, component_name: str) -> str:
        """
        Определить категорию компонента по названию
        
        Args:
            component_name: Название компонента
        
        Returns:
            Категория (atoms, molecules, organisms, templates, pages)
        """
        name_lower = component_name.lower()
        
        # Простая эвристика для определения категории
        if any(word in name_lower for word in ["button", "input", "icon", "badge", "avatar"]):
            return "atoms"
        elif any(word in name_lower for word in ["form", "card", "modal", "dialog", "dropdown"]):
            return "molecules"
        elif any(word in name_lower for word in ["header", "footer", "sidebar", "navbar", "layout"]):
            return "organisms"
        elif any(word in name_lower for word in ["page", "template", "view"]):
            return "templates"
        else:
            return "molecules"  # По умолчанию
    
    async def search(self, query: str, limit: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Семантический поиск компонентов
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            filters: Дополнительные фильтры (например, {"category": "atoms"})
        
        Returns:
            Список найденных компонентов с релевантностью
        """
        # Получаем эмбеддинг запроса
        query_vector = await self._get_embedding(query)
        
        # Подготавливаем фильтры
        qdrant_filter = None
        if filters:
            conditions = []
            if "category" in filters:
                conditions.append(
                    FieldCondition(key="category", match=MatchValue(value=filters["category"]))
                )
            if "package" in filters:
                conditions.append(
                    FieldCondition(key="package", match=MatchValue(value=filters["package"]))
                )
            if "tags" in filters:
                # Для тегов нужна более сложная логика (any match)
                pass
            
            if conditions:
                qdrant_filter = Filter(must=conditions)
        
        # Выполняем поиск
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=qdrant_filter
        )
        
        # Форматируем результаты
        results = []
        for result in search_results:
            results.append({
                "id": result.payload.get("id"),
                "name": result.payload.get("name"),
                "category": result.payload.get("category"),
                "package": result.payload.get("package"),
                "score": result.score,  # Релевантность (0-1)
                "snippet": result.payload.get("text", "")[:200],
                "data": result.payload.get("data", {}),
                "metadata": {
                    "source": result.payload.get("source", "npm"),
                    "indexed_at": result.payload.get("indexed_at"),
                    "tags": result.payload.get("tags", [])
                }
            })
        
        return results
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Получить статистику коллекции
        
        Returns:
            Статистика коллекции
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            stats = {
                "collection_name": self.collection_name,
                "points_count": collection_info.points_count,
            }
            # Добавляем опциональные поля, если они доступны
            if hasattr(collection_info, 'vectors_count'):
                stats["vectors_count"] = collection_info.vectors_count
            if hasattr(collection_info, 'indexed_vectors_count'):
                stats["indexed_vectors_count"] = collection_info.indexed_vectors_count
            if hasattr(collection_info, 'config'):
                stats["vector_size"] = collection_info.config.params.vectors.size if hasattr(collection_info.config.params, 'vectors') else None
            return stats
        except Exception as e:
            return {"error": str(e)}
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.http_client.aclose()

