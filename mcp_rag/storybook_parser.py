"""
Модуль для парсинга компонентов из Storybook
Поддержка извлечения информации о компонентах из Storybook URL
"""
"""
Модуль для парсинга компонентов из Storybook
Поддержка извлечения информации о компонентах из Storybook URL
"""
import httpx
import re
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse, urljoin
from cache_service import CacheService


class StorybookParser:
    """Парсер для извлечения компонентов из Storybook"""
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Инициализация парсера
        
        Args:
            cache_service: Сервис кэширования (опционально)
        """
        self.client = httpx.AsyncClient(
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "User-Agent": "MCP-RAG-Server/1.0.0"
            },
            timeout=30.0,
            follow_redirects=True
        )
        self.cache = cache_service
    
    async def parse_storybook_url(self, storybook_url: str) -> Dict[str, Any]:
        """
        Парсинг компонентов из Storybook URL
        
        Args:
            storybook_url: URL Storybook (например, "https://storybook.example.com")
        
        Returns:
            Словарь с информацией о компонентах из Storybook
        """
        # Проверяем кэш
        if self.cache:
            cache_key = f"storybook:{storybook_url}"
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        
        try:
            # Нормализуем URL
            parsed_url = urlparse(storybook_url)
            if not parsed_url.scheme:
                storybook_url = f"https://{storybook_url}"
            
            # Получаем главную страницу Storybook
            main_page = await self._fetch_page(storybook_url)
            if not main_page:
                return {
                    "error": f"Не удалось загрузить страницу {storybook_url}",
                    "url": storybook_url
                }
            
            # Извлекаем информацию о компонентах
            components = await self._extract_components(main_page, storybook_url)
            
            # Получаем метаданные Storybook
            metadata = await self._extract_metadata(main_page, storybook_url)
            
            result = {
                "url": storybook_url,
                "metadata": metadata,
                "components": components,
                "total_components": len(components),
                "parsed_at": self._get_timestamp()
            }
            
            # Сохраняем в кэш
            if self.cache:
                await self.cache.set(cache_key, json.dumps(result, ensure_ascii=False), ttl=3600)
            
            return result
            
        except Exception as e:
            return {
                "error": str(e),
                "url": storybook_url
            }
    
    async def _fetch_page(self, url: str) -> Optional[str]:
        """Загрузить HTML страницу"""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Ошибка при загрузке страницы {url}: {e}")
            return None
    
    async def _extract_components(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """
        Извлечь информацию о компонентах из HTML Storybook
        
        Storybook обычно использует структуру:
        - Список историй (stories) в навигации
        - Метаданные компонентов в JSON-LD или script тегах
        - Информация о компонентах в DOM
        """
        soup = BeautifulSoup(html, 'html.parser')
        components = []
        
        # Ищем JSON-LD данные (Storybook может использовать их)
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and 'name' in data:
                    components.append({
                        "name": data.get("name", ""),
                        "description": data.get("description", ""),
                        "category": data.get("category", ""),
                        "source": "storybook_jsonld"
                    })
            except:
                pass
        
        # Ищем script теги с данными Storybook
        storybook_scripts = soup.find_all('script', string=re.compile(r'window\.__STORYBOOK'))
        for script in storybook_scripts:
            try:
                # Извлекаем данные из window.__STORYBOOK_*
                script_text = script.string
                # Пытаемся найти JSON данные
                json_match = re.search(r'\{.*\}', script_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    if isinstance(data, dict):
                        stories = data.get('stories', {})
                        for story_id, story_data in stories.items():
                            if isinstance(story_data, dict):
                                components.append({
                                    "id": story_id,
                                    "name": story_data.get("name", story_id),
                                    "title": story_data.get("title", ""),
                                    "description": story_data.get("description", ""),
                                    "category": story_data.get("kind", ""),
                                    "source": "storybook_script"
                                })
            except:
                pass
        
        # Ищем ссылки на истории (stories) в навигации
        nav_links = soup.find_all('a', href=re.compile(r'/.*'))
        story_urls = set()
        for link in nav_links:
            href = link.get('href', '')
            if '/story/' in href or '/?path=/story/' in href:
                story_urls.add(urljoin(base_url, href))
        
        # Извлекаем информацию из URL историй
        for story_url in list(story_urls)[:50]:  # Ограничиваем количество
            story_info = await self._parse_story_page(story_url)
            if story_info:
                components.append(story_info)
        
        # Ищем компоненты в структуре навигации Storybook
        sidebar = soup.find('nav') or soup.find('div', class_=re.compile(r'sidebar|navigation', re.I))
        if sidebar:
            items = sidebar.find_all(['a', 'button', 'div'], class_=re.compile(r'item|story|component', re.I))
            for item in items:
                text = item.get_text(strip=True)
                href = item.get('href', '')
                if text and (href or 'story' in text.lower()):
                    components.append({
                        "name": text,
                        "url": urljoin(base_url, href) if href else None,
                        "source": "storybook_navigation"
                    })
        
        # Удаляем дубликаты по имени
        seen = set()
        unique_components = []
        for comp in components:
            comp_name = comp.get("name", "").lower()
            if comp_name and comp_name not in seen:
                seen.add(comp_name)
                unique_components.append(comp)
        
        return unique_components
    
    async def _parse_story_page(self, story_url: str) -> Optional[Dict[str, Any]]:
        """Парсинг отдельной страницы истории Storybook"""
        try:
            html = await self._fetch_page(story_url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Извлекаем название из заголовка или мета-тегов
            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else ""
            
            # Извлекаем описание из meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ""
            
            # Извлекаем код компонента из iframe или script
            code_blocks = soup.find_all(['pre', 'code', 'script'])
            code_snippet = ""
            for block in code_blocks:
                text = block.get_text(strip=True)
                if 'export' in text or 'function' in text or 'const' in text:
                    code_snippet = text[:500]  # Первые 500 символов
                    break
            
            return {
                "name": title_text.split('|')[0].strip() if '|' in title_text else title_text,
                "description": description,
                "url": story_url,
                "code_snippet": code_snippet,
                "source": "storybook_story"
            }
        except Exception as e:
            print(f"Ошибка при парсинге страницы {story_url}: {e}")
            return None
    
    async def _extract_metadata(self, html: str, base_url: str) -> Dict[str, Any]:
        """Извлечь метаданные Storybook"""
        soup = BeautifulSoup(html, 'html.parser')
        metadata = {}
        
        # Извлекаем title
        title = soup.find('title')
        if title:
            metadata['title'] = title.get_text(strip=True)
        
        # Извлекаем описание
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            metadata['description'] = meta_desc.get('content', '')
        
        # Извлекаем версию Storybook (если есть)
        version_meta = soup.find('meta', attrs={'name': 'storybook-version'})
        if version_meta:
            metadata['storybook_version'] = version_meta.get('content', '')
        
        # Ищем информацию о библиотеке
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title:
            metadata['og_title'] = og_title.get('content', '')
        
        return metadata
    
    def _get_timestamp(self) -> str:
        """Получить текущую временную метку"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.aclose()

