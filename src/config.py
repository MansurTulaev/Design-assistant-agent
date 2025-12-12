"""
Конфигурация сервера.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

@dataclass
class FigmaConfig:
    """Конфигурация Figma API."""
    access_token: str
    base_url: str = "https://api.figma.com/v1"
    timeout: int = 30
    
    @classmethod
    def from_env(cls) -> "FigmaConfig":
        token = os.getenv("FIGMA_ACCESS_TOKEN")
        if not token:
            raise ValueError("FIGMA_ACCESS_TOKEN не задан")
        return cls(
            access_token=token,
            base_url=os.getenv("FIGMA_API_BASE_URL", "https://api.figma.com/v1"),
            timeout=int(os.getenv("FIGMA_REQUEST_TIMEOUT", "30"))
        )

@dataclass
class ServerConfig:
    """Конфигурация сервера."""
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )

@dataclass
class DesignSystemConfig:
    """Конфигурация сканирования дизайн-системы."""
    max_depth: int = 10
    supported_extensions: tuple = (".tsx", ".ts", ".jsx", ".js")
    
    @classmethod
    def from_env(cls) -> "DesignSystemConfig":
        extensions = os.getenv("DS_SUPPORTED_EXTENSIONS", ".tsx,.ts,.jsx,.js")
        return cls(
            max_depth=int(os.getenv("DS_SCAN_MAX_DEPTH", "10")),
            supported_extensions=tuple(ext.split(",") for ext in extensions.split(","))
        )

class Config:
    """Главный класс конфигурации."""
    
    def __init__(self):
        self.figma = FigmaConfig.from_env()
        self.server = ServerConfig.from_env()
        self.design_system = DesignSystemConfig.from_env()

config = Config()