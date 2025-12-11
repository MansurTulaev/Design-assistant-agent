"""MCP сервер для работы с Figma API и Tokens Studio."""

import os
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

# Constants
PORT = int(os.getenv("PORT", "8000"))

# Импортируем единый экземпляр FastMCP
from mcp_instance import mcp

# Используем глобальные настройки вместо deprecated mcp.settings
import fastmcp
fastmcp.settings.port = PORT
fastmcp.settings.host = "0.0.0.0"

# Сначала импортируем prometheus_client для метрик
try:
    from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    print("⚠️ Prometheus Client не установлен, метрики недоступны")
    PROMETHEUS_AVAILABLE = False

# Импортируем инструменты
print("🔧 Загружаем инструменты для Figma Kontur UI Scanner...")
try:
    from tools.get_design_system import get_design_system_components
    print("✅ get_design_system_components загружен")
except Exception as e:
    print(f"❌ Ошибка импорта get_design_system_components: {e}")
    import traceback
    traceback.print_exc()

try:
    from tools.scan_git import scan_git_components
    print("✅ scan_git_components загружен")
except Exception as e:
    print(f"❌ Ошибка импорта scan_git_components: {e}")
    import traceback
    traceback.print_exc()

try:
    from tools.analyze_layout import analyze_figma_layout
    print("✅ analyze_figma_layout загружен")
except Exception as e:
    print(f"❌ Ошибка импорта analyze_figma_layout: {e}")
    import traceback
    traceback.print_exc()

try:
    from tools.map_components import map_layout_to_components
    print("✅ map_layout_to_components загружен")
except Exception as e:
    print(f"❌ Ошибка импорта map_layout_to_components: {e}")
    import traceback
    traceback.print_exc()

print("✅ Все инструменты загружены:")
print("  - get_design_system_components (получение компонентов из дизайн-системы)")
print("  - analyze_figma_layout (анализ макета Figma)")
print("  - map_layout_to_components (сопоставление и генерация кода)")
print("  - scan_git_components (сканирование Git-репозитория Retail UI)")


# ============ СОЗДАЕМ ПРОСТЫЕ ФУНКЦИИ ДЛЯ ENDPOINTS ============

import time
from typing import Dict, Any

# Глобальные переменные для метрик
_request_counter = None
_uptime_gauge = None
_start_time = None

def init_metrics():
    """Инициализация метрик Prometheus."""
    global _request_counter, _uptime_gauge, _start_time
    
    if not PROMETHEUS_AVAILABLE:
        return
    
    try:
        _request_counter = Counter('http_requests_total', 'Total HTTP requests', ['endpoint'])
        _uptime_gauge = Gauge('server_uptime_seconds', 'Server uptime in seconds')
        _start_time = time.time()
        print("✅ Метрики Prometheus инициализированы")
    except Exception as e:
        print(f"⚠️ Не удалось инициализировать метрики: {e}")

def get_health_response() -> Dict[str, Any]:
    """Формирование ответа для health check."""
    return {
        "status": "healthy",
        "service": "mcp-figma-kontur",
        "version": "0.1.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

def get_root_response() -> Dict[str, Any]:
    """Формирование ответа для корневого endpoint."""
    return {
        "service": "MCP Figma Kontur UI Scanner",
        "version": "0.1.0",
        "description": "MCP сервер для сканирования Figma дизайн-системы Kontur UI",
        "endpoints": {
            "mcp": f"http://0.0.0.0:{PORT}/mcp",
            "health": f"http://0.0.0.0:{PORT}/health",
            "metrics": f"http://0.0.0.0:{PORT}/metrics"
        },
        "tools": [
            "get_design_system_components",
            "analyze_figma_layout", 
            "map_layout_to_components"
        ],
        "figma_files": {
            "design_system": os.getenv("KONTUR_UI_FILE_ID", "KQc2jUV5CuCDqZ7hHTX0vc"),
            "test_file": os.getenv("TEST_FILE_ID", "d4qp6XOTZc3abUbq5UUDe7")
        }
    }

# ============ РЕГИСТРИРУЕМ КАСТОМНЫЕ TOOLS ДЛЯ ENDPOINTS ============

# Эти tools будут выглядеть как обычные инструменты MCP, но возвращать HTTP-ответы

@mcp.tool()
async def http_health(ctx=None) -> Dict[str, Any]:
    """
    Health check endpoint для мониторинга состояния сервера.
    
    Returns:
        Dict с информацией о состоянии сервера.
    """
    global _request_counter
    
    if _request_counter:
        _request_counter.labels(endpoint='health').inc()
        _uptime_gauge.set(time.time() - _start_time)
    
    return get_health_response()

@mcp.tool()
async def http_metrics(ctx=None) -> Dict[str, Any]:
    """
    Prometheus metrics endpoint.
    
    Returns:
        Метрики в формате Prometheus или сообщение об ошибке.
    """
    global _request_counter
    
    if _request_counter:
        _request_counter.labels(endpoint='metrics').inc()
    
    if not PROMETHEUS_AVAILABLE:
        return {"error": "Prometheus client not available"}
    
    try:
        # Генерируем метрики
        metrics_data = generate_latest().decode('utf-8')
        
        # Возвращаем как текст
        # Note: MCP обычно ожидает JSON, но для метрик можно вернуть текст
        return {
            "content_type": "text/plain; version=0.0.4",
            "metrics": metrics_data
        }
    except Exception as e:
        return {"error": f"Failed to generate metrics: {str(e)}"}

@mcp.tool()
async def http_root(ctx=None) -> Dict[str, Any]:
    """
    Корневой endpoint с информацией о сервере.
    
    Returns:
        Dict с информацией о сервере и доступных endpoints.
    """
    global _request_counter
    
    if _request_counter:
        _request_counter.labels(endpoint='root').inc()
    
    return get_root_response()

# ============ ГЛАВНАЯ ФУНКЦИЯ ============

def main():
    """Запуск MCP сервера с HTTP транспортом."""
    print("=" * 60)
    print("🌐 ЗАПУСК MCP FIGMA KONTUR UI SCANNER")
    print("=" * 60)
    print(f"🚀 MCP Server: http://0.0.0.0:{PORT}/mcp")
    print("📋 Доступные инструменты через MCP:")
    print("  1. get_design_system_components - Получить компоненты дизайн-системы")
    print("  2. analyze_figma_layout - Анализировать макет Figma")
    print("  3. map_layout_to_components - Сопоставить макет с компонентами")
    print("  4. http_health - Health check (имитация /health)")
    print("  5. http_metrics - Prometheus метрики (имитация /metrics)")
    print("  6. http_root - Информация о сервере (имитация /)")
    print("=" * 60)
    print("ℹ️  Для доступа к health check и metrics используйте MCP инструменты")
    print("   Пример: вызовите инструмент 'http_health' для проверки состояния")
    print("=" * 60)
    print("⏳ Запускаем сервер...")
    
    # Инициализируем метрики
    init_metrics()
    
    try:
        # Запускаем MCP сервер
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=PORT
        )
    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал остановки (Ctrl+C)")
        print("🔄 Выполняем graceful shutdown...")
        print("✅ Сервер остановлен")
    except Exception as e:
        print(f"❌ Ошибка запуска сервера: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()