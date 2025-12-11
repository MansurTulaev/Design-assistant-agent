import pytest
import os
from unittest.mock import patch, Mock, MagicMock
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset

from src.agent import worker_agent, get_system_prompt, llm_model


class TestAgentModule:
    """Тесты для модуля agent.py"""
    
    @patch('src.agent.open')
    def test_get_system_prompt_from_file(self, mock_open, tmp_path):
        """Тест загрузки системного промпта из файла"""
        # Создаем тестовый файл
        test_file = tmp_path / "test_prompt.txt"
        test_file.write_text("Test system prompt content")
        
        with patch('src.agent.os.getenv') as mock_getenv:
            mock_getenv.return_value = str(test_file)
            
            prompt = get_system_prompt()
            
            assert prompt == "Test system prompt content"
            mock_open.assert_called_once_with(str(test_file), 'r', encoding='utf-8')
    
    def test_get_system_prompt_fallback(self):
        """Тест fallback на переменную окружения"""
        with patch('src.agent.open', side_effect=FileNotFoundError):
            with patch('src.agent.os.getenv') as mock_getenv:
                mock_getenv.side_effect = lambda key, default=None: {
                    'AGENT_SYSTEM_PROMPT_FILE': '/nonexistent',
                    'AGENT_SYSTEM_PROMPT': 'Fallback prompt'
                }.get(key, default)
                
                prompt = get_system_prompt()
                
                assert prompt == "Fallback prompt"
    
    def test_llm_model_configuration(self, test_env_vars):
        """Тест конфигурации LLM модели"""
        assert isinstance(llm_model, LiteLlm)
        assert llm_model.model == "test-model"
        assert llm_model.api_base == "https://test-api.example.com"
        assert llm_model.api_key == "test-key"
    
    @patch('src.agent.McpToolset')
    def test_mcp_tools_creation(self, mock_mcp_toolset):
        """Тест создания MCP инструментов"""
        test_urls = "http://mcp1:8000/sse,http://mcp2:8000/sse"
        
        with patch('src.agent.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                'MCP_URL': test_urls,
                'AGENT_SYSTEM_PROMPT': 'test'
            }.get(key, default)
            
            # Переимпортируем модуль для применения патчей
            import importlib
            import src.agent
            importlib.reload(src.agent)
            
            # Проверяем, что McpToolset был вызван для каждого URL
            assert mock_mcp_toolset.call_count == 2
            
            calls = mock_mcp_toolset.call_args_list
            assert 'http://mcp1:8000/sse' in str(calls[0])
            assert 'http://mcp2:8000/sse' in str(calls[1])
    
    def test_worker_agent_creation(self):
        """Тест создания основного агента"""
        assert isinstance(worker_agent, Agent)
        assert worker_agent.name == "TestAgent"
        assert worker_agent.description == "Test Description"
        
        # Проверяем наличие инструментов
        assert hasattr(worker_agent, 'tools')
        
        # Проверяем конфигурацию модели
        assert worker_agent.model.model == "test-model"
    
    @patch('src.agent.load_dotenv')
    def test_module_import_without_errors(self, mock_load_dotenv):
        """Тест, что модуль импортируется без ошибок"""
        # Проверяем, что все необходимые объекты созданы
        assert 'worker_agent' in globals()
        assert 'llm_model' in globals()
        assert 'root_agent' in globals()
        
        mock_load_dotenv.assert_called_once()
    
    def test_agent_handoff_configuration(self):
        """Тест конфигурации handoff агента"""
        assert worker_agent.handoff_description == \
            "I can use Figma and design system tools to generate React code"
    
    @pytest.mark.parametrize("env_var,expected", [
        ("AGENT_NAME", "TestAgent"),
        ("AGENT_DESCRIPTION", "Test Description"),
        ("LLM_MODEL", "test-model"),
    ])
    def test_environment_variables_used(self, env_var, expected, test_env_vars):
        """Параметризованный тест использования переменных окружения"""
        # Проверяем, что значения используются в агенте
        if env_var == "AGENT_NAME":
            assert worker_agent.name == expected.replace(" ", "_")
        elif env_var == "AGENT_DESCRIPTION":
            assert worker_agent.description == expected
        elif env_var == "LLM_MODEL":
            assert worker_agent.model.model == expected