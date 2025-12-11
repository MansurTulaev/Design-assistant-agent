import pytest
import asyncio
import os
from unittest.mock import patch, AsyncMock
from a2a.server.events import EventQueue
from a2a.types import TaskState

from src.agent import worker_agent
from src.a2a_agent import A2Aagent
from src.agent_task_manager import MyAgentExecutor


class TestIntegration:
    """Интеграционные тесты полного потока"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_react_generation_flow(self):
        """Тест полного потока генерации React компонента"""
        # 1. Создаем executor
        executor = MyAgentExecutor()
        
        # 2. Мокаем внешние зависимости
        mock_context = AsyncMock()
        mock_context.get_user_input.return_value = "Create a login form"
        mock_context.current_task = None
        mock_context.message = AsyncMock()
        
        mock_event_queue = AsyncMock()
        mock_event_queue.enqueue_event = AsyncMock()
        
        # 3. Мокаем stream агента с реалистичными ответами
        mock_stream_responses = [
            # Промежуточный статус
            {
                "is_task_complete": False,
                "require_user_input": False,
                "content": "🔄 Analyzing Figma structure...",
                "is_error": False,
                "is_event": True
            },
            # Еще один промежуточный статус
            {
                "is_task_complete": False,
                "require_user_input": False,
                "content": "🔄 Fetching component metadata...",
                "is_error": False,
                "is_event": True
            },
            # Финальный результат
            {
                "is_task_complete": True,
                "require_user_input": False,
                "content": """```tsx
import { Card, Input, Button, Stack } from '@design-system/core';

interface LoginFormProps {
  onSubmit: (email: string, password: string) => void;
}

export const LoginForm = ({ onSubmit }: LoginFormProps) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(email, password);
  };

  return (
    <Card variant="outlined" padding="xl">
      <form onSubmit={handleSubmit}>
        <Stack spacing="md">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Button type="submit" variant="primary" fullWidth>
            Sign In
          </Button>
        </Stack>
      </form>
    </Card>
  );
};
```""",
                "is_error": False,
                "is_event": False
            }
        ]
        
        async def mock_stream_generator():
            for response in mock_stream_responses:
                yield response
        
        executor.agent.stream = AsyncMock(return_value=mock_stream_generator())
        
        # 4. Мокаем TaskUpdater
        with patch('src.agent_task_manager.TaskUpdater') as mock_updater_class:
            mock_updater = AsyncMock()
            mock_updater.update_status = AsyncMock()
            mock_updater_class.return_value = mock_updater
            
            # 5. Выполняем
            await executor.execute(mock_context, mock_event_queue)
            
            # 6. Проверяем вызовы
            # Должно быть 3 вызова update_status
            assert mock_updater.update_status.call_count == 3
            
            calls = mock_updater.update_status.call_args_list
            
            # Первые два вызова - working state
            assert calls[0][0][0] == TaskState.working
            assert calls[1][0][0] == TaskState.working
            
            # Последний вызов - completed
            assert calls[2][0][0] == TaskState.completed
            
            # Проверяем содержимое последнего ответа
            last_message = calls[2][0][1].content
            assert "import" in last_message
            assert "LoginForm" in last_message
            assert "@design-system/core" in last_message
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_with_mcp_tools(self):
        """Тест взаимодействия агента с MCP инструментами"""
        # Создаем реального агента (но с моками LLM)
        with patch('google.adk.models.lite_llm.LiteLlm') as mock_llm:
            # Настраиваем мок LLM
            mock_llm_instance = AsyncMock()
            
            async def mock_generate(*args, **kwargs):
                class MockChoice:
                    def __init__(self):
                        self.message = AsyncMock()
                        self.message.content = "Generated React component code"
                
                class MockResponse:
                    def __init__(self):
                        self.choices = [MockChoice()]
                
                return MockResponse()
            
            mock_llm_instance.generate = mock_generate
            mock_llm.return_value = mock_llm_instance
            
            # Переимпортируем agent для применения моков
            import importlib
            import sys
            if 'src.agent' in sys.modules:
                importlib.reload(sys.modules['src.agent'])
            
            from src.agent import worker_agent
            
            # Проверяем, что агент создан с инструментами
            assert worker_agent.tools is not None
            
            # Проверяем основные свойства
            assert worker_agent.name == "TestAgent"
            assert "React" in worker_agent.description
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_recovery_flow(self):
        """Тест потока восстановления после ошибки"""
        executor = MyAgentExecutor()
        
        # Симулируем ошибку, затем успешное выполнение
        call_count = 0
        
        async def mock_stream_with_recovery():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # Первый вызов - ошибка
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "Error: Figma API unavailable",
                    "is_error": True,
                    "is_event": False
                }
            else:
                # Второй вызов - успех
                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": "Successfully generated component",
                    "is_error": False,
                    "is_event": False
                }
        
        executor.agent.stream = AsyncMock(side_effect=mock_stream_with_recovery)
        
        mock_context = AsyncMock()
        mock_context.get_user_input.return_value = "Create button"
        mock_context.current_task = None
        mock_context.message = AsyncMock()
        
        mock_event_queue = AsyncMock()
        mock_event_queue.enqueue_event = AsyncMock()
        
        with patch('src.agent_task_manager.TaskUpdater') as mock_updater_class:
            mock_updater = AsyncMock()
            mock_updater.update_status = AsyncMock()
            mock_updater_class.return_value = mock_updater
            
            # Первое выполнение - ошибка
            await executor.execute(mock_context, mock_event_queue)
            
            # Проверяем, что статус установлен в failed
            mock_updater.update_status.assert_called_once()
            call_args = mock_updater.update_status.call_args
            assert call_args[0][0] == TaskState.failed
            assert "Error:" in call_args[0][1].content
    
    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_executions(self):
        """Тест конкурентных выполнений (медленный тест)"""
        executor = MyAgentExecutor()
        
        async def mock_stream(query, session_id):
            await asyncio.sleep(0.1)  # Имитация работы
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"Response to: {query}",
                "is_error": False,
                "is_event": False
            }
        
        executor.agent.stream = AsyncMock(side_effect=mock_stream)
        
        # Запускаем несколько задач concurrently
        tasks = []
        for i in range(3):
            mock_context = AsyncMock()
            mock_context.get_user_input.return_value = f"Query {i}"
            mock_context.current_task = None
            mock_context.message = AsyncMock()
            
            mock_event_queue = AsyncMock()
            mock_event_queue.enqueue_event = AsyncMock()
            
            with patch('src.agent_task_manager.TaskUpdater') as mock_updater_class:
                mock_updater = AsyncMock()
                mock_updater.update_status = AsyncMock()
                mock_updater_class.return_value = mock_updater
                
                task = asyncio.create_task(
                    executor.execute(mock_context, mock_event_queue)
                )
                tasks.append((task, mock_updater))
        
        # Ждем завершения всех задач
        await asyncio.gather(*[task for task, _ in tasks])
        
        # Проверяем, что все задачи завершились
        for task, mock_updater in tasks:
            assert task.done()
            mock_updater.update_status.assert_called_once()