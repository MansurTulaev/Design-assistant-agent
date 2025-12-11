import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.types import Task, TaskState
from a2a.utils import new_agent_text_message

from src.agent_task_manager import MyAgentExecutor


class TestMyAgentExecutor:
    """Тесты для MyAgentExecutor"""
    
    @pytest.fixture
    def executor(self):
        return MyAgentExecutor()
    
    @pytest.fixture
    def mock_context(self):
        context = Mock(spec=RequestContext)
        context.get_user_input.return_value = "Test query"
        context.current_task = None
        context.message = Mock()
        return context
    
    @pytest.fixture
    def mock_event_queue(self):
        queue = Mock(spec=EventQueue)
        queue.enqueue_event = AsyncMock()
        return queue
    
    @pytest.fixture
    def mock_task(self):
        task = Mock(spec=Task)
        task.id = "task-123"
        task.context_id = "context-123"
        task.state = TaskState.pending
        return task
    
    @pytest.mark.asyncio
    async def test_execute_with_new_task(self, executor, mock_context, mock_event_queue):
        """Тест выполнения с созданием новой задачи"""
        mock_context.current_task = None
        
        with patch('src.agent_task_manager.new_task') as mock_new_task:
            with patch('src.agent_task_manager.TaskUpdater') as mock_updater_class:
                # Настраиваем моки
                mock_task = Mock()
                mock_task.id = "new-task-123"
                mock_task.context_id = "new-context-123"
                mock_new_task.return_value = mock_task
                
                mock_updater = Mock()
                mock_updater.update_status = AsyncMock()
                mock_updater_class.return_value = mock_updater
                
                # Мок для stream агента
                mock_stream_items = [
                    {
                        "is_task_complete": False,
                        "require_user_input": False,
                        "content": "Processing...",
                        "is_error": False,
                        "is_event": True
                    },
                    {
                        "is_task_complete": True,
                        "require_user_input": False,
                        "content": "Final result",
                        "is_error": False,
                        "is_event": False
                    }
                ]
                
                async def mock_stream_generator():
                    for item in mock_stream_items:
                        yield item
                
                executor.agent.stream = AsyncMock(return_value=mock_stream_generator())
                
                # Выполняем
                await executor.execute(mock_context, mock_event_queue)
                
                # Проверяем
                mock_new_task.assert_called_once_with(mock_context.message)
                mock_event_queue.enqueue_event.assert_called_once_with(mock_task)
                
                # Проверяем вызовы update_status
                assert mock_updater.update_status.call_count == 2
                
                # Первый вызов - working state
                first_call = mock_updater.update_status.call_args_list[0]
                assert first_call[0][0] == TaskState.working
                
                # Второй вызов - completed state
                second_call = mock_updater.update_status.call_args_list[1]
                assert second_call[0][0] == TaskState.completed
    
    @pytest.mark.asyncio
    async def test_execute_with_existing_task(self, executor, mock_context, mock_event_queue, mock_task):
        """Тест выполнения с существующей задачей"""
        mock_context.current_task = mock_task
        
        with patch('src.agent_task_manager.TaskUpdater') as mock_updater_class:
            mock_updater = Mock()
            mock_updater.update_status = AsyncMock()
            mock_updater_class.return_value = mock_updater
            
            # Мок для stream
            async def mock_stream_generator():
                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": "Result",
                    "is_error": False,
                    "is_event": False
                }
            
            executor.agent.stream = AsyncMock(return_value=mock_stream_generator())
            
            await executor.execute(mock_context, mock_event_queue)
            
            # Не должна создаваться новая задача
            mock_event_queue.enqueue_event.assert_not_called()
            
            # Должен использоваться существующий task ID
            mock_updater_class.assert_called_once_with(
                mock_event_queue, "task-123", "context-123"
            )
    
    @pytest.mark.asyncio
    async def test_execute_with_error(self, executor, mock_context, mock_event_queue):
        """Тест выполнения с ошибкой"""
        with patch('src.agent_task_manager.new_task'):
            with patch('src.agent_task_manager.TaskUpdater') as mock_updater_class:
                mock_updater = Mock()
                mock_updater.update_status = AsyncMock()
                mock_updater_class.return_value = mock_updater
                
                # Мок stream с ошибкой
                async def mock_stream_generator():
                    yield {
                        "is_task_complete": False,
                        "require_user_input": False,
                        "content": "Error occurred",
                        "is_error": True,
                        "is_event": False
                    }
                
                executor.agent.stream = AsyncMock(return_value=mock_stream_generator())
                
                await executor.execute(mock_context, mock_event_queue)
                
                # Проверяем, что статус установлен в failed
                mock_updater.update_status.assert_called_once()
                call_args = mock_updater.update_status.call_args
                assert call_args[0][0] == TaskState.failed
    
    @pytest.mark.asyncio
    async def test_execute_with_input_required(self, executor, mock_context, mock_event_queue):
        """Тест выполнения, требующего ввода пользователя"""
        with patch('src.agent_task_manager.new_task'):
            with patch('src.agent_task_manager.TaskUpdater') as mock_updater_class:
                mock_updater = Mock()
                mock_updater.update_status = AsyncMock()
                mock_updater_class.return_value = mock_updater
                
                async def mock_stream_generator():
                    yield {
                        "is_task_complete": False,
                        "require_user_input": True,
                        "content": "Need more information",
                        "is_error": False,
                        "is_event": False
                    }
                
                executor.agent.stream = AsyncMock(return_value=mock_stream_generator())
                
                await executor.execute(mock_context, mock_event_queue)
                
                mock_updater.update_status.assert_called_once()
                call_args = mock_updater.update_status.call_args
                assert call_args[0][0] == TaskState.input_required
    
    @pytest.mark.asyncio
    async def test_execute_stream_exception(self, executor, mock_context, mock_event_queue):
        """Тест исключения в stream"""
        with patch('src.agent_task_manager.new_task'):
            with patch('src.agent_task_manager.TaskUpdater') as mock_updater_class:
                mock_updater = Mock()
                mock_updater.update_status = AsyncMock()
                mock_updater_class.return_value = mock_updater
                
                # Исключение в stream
                executor.agent.stream = AsyncMock(side_effect=Exception("Stream error"))
                
                await executor.execute(mock_context, mock_event_queue)
                
                # Должна быть установлена ошибка
                mock_updater.update_status.assert_called_once()
                call_args = mock_updater.update_status.call_args
                assert call_args[0][0] == TaskState.failed
                assert "Stream error" in call_args[0][1].content
    
    @pytest.mark.asyncio
    async def test_cancel_unsupported(self, executor):
        """Тест отмены задачи (не поддерживается)"""
        from a2a.utils.errors import ServerError
        from a2a.types import UnsupportedOperationError
        
        with pytest.raises(ServerError) as exc_info:
            await executor.cancel(Mock(), Mock())
        
        assert isinstance(exc_info.value.error, UnsupportedOperationError)
    
    def test_executor_initialization(self, executor):
        """Тест инициализации executor"""
        assert hasattr(executor, 'agent')
        assert hasattr(executor, 'logger')
        assert executor.logger.name == 'tests.test_agent_task_manager'
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("state_transitions", [
        # (is_task_complete, require_user_input, expected_state)
        (False, False, TaskState.working),
        (False, True, TaskState.input_required),
        (True, False, TaskState.completed),
    ])
    async def test_state_transitions(self, executor, mock_context, mock_event_queue, state_transitions):
        """Параметризованный тест переходов состояний"""
        is_task_complete, require_user_input, expected_state = state_transitions
        
        with patch('src.agent_task_manager.new_task'):
            with patch('src.agent_task_manager.TaskUpdater') as mock_updater_class:
                mock_updater = Mock()
                mock_updater.update_status = AsyncMock()
                mock_updater_class.return_value = mock_updater
                
                async def mock_stream_generator():
                    yield {
                        "is_task_complete": is_task_complete,
                        "require_user_input": require_user_input,
                        "content": f"State: {expected_state}",
                        "is_error": False,
                        "is_event": False
                    }
                
                executor.agent.stream = AsyncMock(return_value=mock_stream_generator())
                
                await executor.execute(mock_context, mock_event_queue)
                
                mock_updater.update_status.assert_called_once()
                call_args = mock_updater.update_status.call_args
                assert call_args[0][0] == expected_state