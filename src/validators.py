"""
Валидаторы входных данных.
"""
import re
from urllib.parse import urlparse

def validate_figma_file_key(file_key: str) -> bool:
    """Валидирует ключ файла Figma."""
    if not file_key or not isinstance(file_key, str):
        return False
    
    pattern = r'^[a-zA-Z0-9_-]{16,32}$'
    return bool(re.match(pattern, file_key))

def validate_figma_url(url: str) -> str:
    """Извлекает ключ файла из URL Figma."""
    try:
        parsed = urlparse(url)
        
        if parsed.netloc not in ["www.figma.com", "figma.com"]:
            return None
        
        path_parts = parsed.path.strip('/').split('/')
        
        if len(path_parts) >= 2 and path_parts[0] == 'file':
            file_key = path_parts[1]
            if validate_figma_file_key(file_key):
                return file_key
        
        return None
        
    except Exception:
        return None