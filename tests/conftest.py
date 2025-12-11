import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock, MagicMock
from typing import Dict, Any, AsyncGenerator
import pytest
from dotenv import load_dotenv

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Загружаем тестовое окружение
load_dotenv('.env.test')

@pytest.fixture
def event_loop():
    """Создаем event loop для асинхронных тестов"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture
def mock_mcp_tool():
    """Мок для MCP инструмента"""
    mock = AsyncMock()
    mock.name = "test_tool"
    mock.description = "Test tool description"
    mock.inputSchema = {"type": "object"}
    return mock

@pytest.fixture
def mock_llm_model():
    """Мок для LLM модели"""
    mock = AsyncMock()
    
    async def mock_generate(*args, **kwargs):
        class MockResponse:
            def __init__(self):
                self.choices = [Mock(message=Mock(content="Generated response"))]
        
        return MockResponse()
    
    mock.generate = mock_generate
    return mock

@pytest.fixture
def mock_session():
    """Мок для сессии"""
    session = Mock()
    session.id = "test-session-123"
    session.user_id = "test-user"
    session.metadata = {}
    return session

@pytest.fixture
def mock_runner():
    """Мок для Google ADK Runner"""
    runner = Mock()
    
    # Мок для run_async
    async def mock_run_async(*args, **kwargs):
        class MockEvent:
            def __init__(self):
                self.content = Mock()
                self.content.parts = [Mock(text="Test response")]
        
        yield MockEvent()
    
    runner.run_async = mock_run_async
    runner.session_service = Mock()
    return runner

@pytest.fixture
def sample_react_code():
    """Пример React кода для тестов"""
    return """import { Button, Card } from '@design-system/core';

interface TestProps {
  title: string;
}

export const TestComponent = ({ title }: TestProps) => (
  <Card>
    <h1>{title}</h1>
    <Button variant="primary">Click me</Button>
  </Card>
);"""

@pytest.fixture
def test_env_vars(monkeypatch):
    """Устанавливаем тестовые переменные окружения"""
    env_vars = {
        "AGENT_NAME": "TestAgent",
        "AGENT_DESCRIPTION": "Test Description",
        "LLM_MODEL": "test-model",
        "LLM_API_BASE": "https://test-api.example.com",
        "LLM_API_KEY": "test-key",
        "MCP_URL": "http://test-mcp:8000/sse",
        "PORT": "9999",
        "ENABLE_PHOENIX": "false",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars

@pytest.fixture
def agent_config_dir(tmp_path):
    """Создаем временную директорию с конфигами агента"""
    config_dir = tmp_path / "agent-config"
    config_dir.mkdir()
    
    # Создаем тестовый промпт
    prompt_file = config_dir / "system-prompt.txt"
    prompt_file.write_text("Test system prompt")
    
    return config_dir