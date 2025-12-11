import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any
from google.genai import types
from google.adk import Runner
from google.adk.sessions import Session

from src.a2a_agent import A2Aagent


class TestA2AAgent:
    """Тесты для A2Aagent класса"""
    
    @pytest.fixture
    def agent(self):
        """Создаем экземпляр агента для тестов"""
        return A2Aagent()
    
    @pytest.fixture
    def mock_runner(self):
        """Мок для Runner"""
        runner = Mock(spec=Runner)
        
        # Мок для run_async
        async def mock_run_async(*args, **kwargs):
            class MockEvent:
                def __init__(self, text):
                    self.content = Mock()
                    self.content.parts = [Mock(text=text)]
            
            yield MockEvent("Test response 1")
            yield MockEvent("Test response 2")
        
        runner.run_async = mock_run_async
        
        # Мок для session_service
        runner.session_service = Mock()
        return runner
    
    @pytest.mark.asyncio
    async def test_get_session_existing(self, agent, mock_session):
        """Тест получения существующей сессии"""
        with patch.object(agent.runner.session_service, 'get_session') as mock_get:
            mock_get.return_value = mock_session
            
            session = await agent.get_session("test-session-id")
            
            assert session == mock_session
            mock_get.assert_called_once_with(
                app_name=agent.agent.name,
                user_id='a2a_user',
                session_id="test-session-id"
            )
    
    @pytest.mark.asyncio
    async def test_get_session_new(self, agent, mock_session):
        """Тест создания новой сессии"""
        with patch.object(agent.runner.session_service, 'get_session') as mock_get:
            with patch.object(agent.runner.session_service, 'create_session') as mock_create:
                mock_get.return_value = None
                mock_create.return_value = mock_session
                
                session = await agent.get_session("new-session-id")
                
                assert session == mock_session
                mock_get.assert_called_once()
                mock_create.assert_called_once_with(
                    app_name=agent.agent.name,
                    user_id='a2a_user',
                    session_id="new-session-id"
                )
    
    @pytest.mark.asyncio
    async def test_invoke_basic(self, agent):
        """Базовый тест синхронного вызова"""
        with patch.object(agent, 'get_session') as mock_get_session:
            with patch.object(agent.runner, 'run_async') as mock_run:
                # Настраиваем моки
                mock_session = Mock()
                mock_session.id = "session-123"
                mock_session.user_id = "user-123"
                mock_get_session.return_value = mock_session
                
                # Мок для асинхронного генератора
                async def mock_run_generator():
                    class MockEvent:
                        def __init__(self):
                            self.content = Mock()
                            self.content.parts = [Mock(text="Final response")]
                    
                    yield MockEvent()
                
                mock_run.return_value = mock_run_generator()
                
                # Вызываем метод
                result = await agent.invoke("Test query", "session-123")
                
                # Проверяем результат
                assert result["is_task_complete"] == True
                assert result["is_error"] == False
                assert result["content"] == "Final response"
                assert result["require_user_input"] == False
                
                # Проверяем вызовы
                mock_get_session.assert_called_once_with("session-123")
                mock_run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stream_with_function_calls(self, agent):
        """Тест стриминга с function calls"""
        with patch.object(agent, 'get_session') as mock_get_session:
            with patch.object(agent.runner, 'run_async') as mock_run:
                # Настраиваем моки
                mock_session = Mock()
                mock_get_session.return_value = mock_session
                
                # Создаем mock события с function call
                async def mock_run_generator():
                    class MockEventWithFunctionCall:
                        def __init__(self):
                            self.content = Mock()
                            mock_part = Mock()
                            mock_part.function_call = Mock()
                            mock_part.function_call.args = {'action': 'Processing Figma structure'}
                            self.content.parts = [mock_part]
                    
                    class MockEventWithText:
                        def __init__(self):
                            self.content = Mock()
                            self.content.parts = [Mock(text="Generated React code")]
                    
                    yield MockEventWithFunctionCall()
                    yield MockEventWithText()
                
                mock_run.return_value = mock_run_generator()
                
                # Собираем результаты
                results = []
                async for item in agent.stream("Generate component", "session-123"):
                    results.append(item)
                
                # Проверяем результаты
                assert len(results) == 2
                
                # Первый элемент - event с function call
                assert results[0]["is_event"] == True
                assert "Processing Figma structure" in results[0]["content"]
                
                # Второй элемент - финальный ответ
                assert results[1]["is_task_complete"] == True
                assert "Generated React code" in results[1]["content"]
    
    @pytest.mark.asyncio
    async def test_stream_empty_response(self, agent):
        """Тест стриминга с пустым ответом"""
        with patch.object(agent, 'get_session'):
            with patch.object(agent.runner, 'run_async') as mock_run:
                # Мок с пустым событием
                async def empty_generator():
                    class EmptyEvent:
                        def __init__(self):
                            self.content = Mock()
                            self.content.parts = []
                    
                    yield EmptyEvent()
                
                mock_run.return_value = empty_generator()
                
                results = []
                async for item in agent.stream("test", "session"):
                    results.append(item)
                
                # Должен вернуться пустой список, так как нет частей с текстом
                assert len(results) == 0
    
    def test_sync_invoke_wrapper(self, agent):
        """Тест синхронной обертки"""
        with patch.object(agent, 'invoke') as mock_invoke:
            mock_invoke.return_value = {"test": "result"}
            
            result = agent.sync_invoke("test query", "session-123")
            
            assert result == {"test": "result"}
            mock_invoke.assert_called_once_with("test query", "session-123")
    
    def test_supported_content_types(self, agent):
        """Тест поддерживаемых типов контента"""
        assert agent.SUPPORTED_CONTENT_TYPES == ["text", "text/plain"]
    
    @pytest.mark.asyncio
    async def test_error_handling_in_stream(self, agent):
        """Тест обработки ошибок в стриме"""
        with patch.object(agent, 'get_session'):
            with patch.object(agent.runner, 'run_async', side_effect=Exception("Test error")):
                
                with pytest.raises(Exception) as exc_info:
                    async for _ in agent.stream("test", "session"):
                        pass
                
                assert "Test error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_call_count", [
        ("simple", 1),
        ("", 1),
        ("complex query with details", 1),
    ])
    async def test_invoke_with_different_queries(self, agent, query, expected_call_count):
        """Параметризованный тест с разными запросами"""
        with patch.object(agent, 'get_session'):
            with patch.object(agent.runner, 'run_async') as mock_run:
                async def mock_generator():
                    class MockEvent:
                        def __init__(self):
                            self.content = Mock()
                            self.content.parts = [Mock(text="Response")]
                    
                    yield MockEvent()
                
                mock_run.return_value = mock_generator()
                
                await agent.invoke(query, "session")
                
                assert mock_run.call_count == expected_call_count