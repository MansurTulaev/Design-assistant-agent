"""
LangChain агент для работы с несколькими MCP серверами
"""
import os
import asyncio
from typing import List, Optional
from langchain_core.tools import Tool
from langchain.agents import create_agent as langchain_create_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama

# Импорты для работы с MCP
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.sessions import StdioConnection, StreamableHttpConnection
    MCP_AVAILABLE = True
except ImportError:
    print("Warning: langchain-mcp-adapters не установлен. Установите: pip install langchain-mcp-adapters")
    MCP_AVAILABLE = False
    StdioConnection = None
    StreamableHttpConnection = None


class MultiMCPAgent:
    """
    Агент LangChain для работы с несколькими MCP серверами
    """
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        mcp_servers: Optional[List[dict]] = None,
        verbose: bool = True
    ):
        """
        Инициализация агента
        
        Args:
            llm: Языковая модель для агента (если None, будет использована модель из env)
            mcp_servers: Список конфигураций MCP серверов
                        [{"name": "mcp_rag", "command": "python", "args": ["path/to/server.py"]}]
            verbose: Выводить ли подробную информацию
        """
        self.verbose = verbose
        self.llm = llm or self._create_llm()
        self.mcp_servers = mcp_servers or self._get_default_mcp_servers()
        self.tools = []
        self.agent_graph = None  # LangGraph граф агента
        self.mcp_client = None  # Клиент для MCP серверов
        self.checkpointer = MemorySaver()  # Чекпоинтер для состояния
        
    def _create_llm(self) -> BaseChatModel:
        """Создать LLM из переменных окружения"""
        # Проверяем доступные провайдеры
        if os.getenv("OPENAI_API_KEY"):
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            return ChatOpenAI(model=model, temperature=0)
        
        elif os.getenv("ANTHROPIC_API_KEY"):
            model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            return ChatAnthropic(model=model, temperature=0)
        
        elif os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST"):
            # Пробуем подключиться к Ollama
            base_url = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
            model = os.getenv("OLLAMA_MODEL", "llama3.2")
            try:
                return ChatOllama(base_url=base_url, model=model, temperature=0)
            except Exception as e:
                print(f"Warning: Не удалось подключиться к Ollama: {e}")
        
        # Fallback на OpenAI (даже без ключа, для демонстрации структуры)
        print("Warning: Не найдены API ключи. Используйте OPENAI_API_KEY, ANTHROPIC_API_KEY или OLLAMA_BASE_URL")
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    def _get_default_mcp_servers(self) -> List[dict]:
        """Получить конфигурации MCP серверов по умолчанию"""
        # Путь к MCP серверу относительно корня проекта
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mcp_rag_path = os.path.join(project_root, "mcp_rag", "main.py")
        
        servers = []
        
        # MCP RAG сервер
        # В Docker используем абсолютный путь, локально - относительный
        if os.path.exists(mcp_rag_path):
            servers.append({
                "name": "mcp_rag",
                "command": "python",
                "args": [mcp_rag_path]
            })
        else:
            # Пробуем абсолютный путь для Docker
            docker_path = "/app/mcp_rag/main.py"
            if os.path.exists(docker_path):
                servers.append({
                    "name": "mcp_rag",
                    "command": "python",
                    "args": [docker_path]
                })
        
        return servers
    
    async def _load_mcp_tools(self) -> List[Tool]:
        """Загрузить инструменты из всех MCP серверов"""
        if not MCP_AVAILABLE:
            print("Error: langchain-mcp-adapters не установлен")
            return []
        
        try:
            # Подготавливаем соединения для MultiServerMCPClient
            connections = {}
            for server_config in self.mcp_servers:
                server_name = server_config["name"]
                
                # Определяем тип транспорта
                if "url" in server_config:
                    # HTTP транспорт
                    connections[server_name] = StreamableHttpConnection(
                        url=server_config["url"]
                    )
                else:
                    # Stdio транспорт (по умолчанию)
                    # StdioConnection возвращает словарь конфигурации
                    stdio_config = StdioConnection(
                        command=server_config["command"],
                        args=server_config.get("args", []),
                        env=server_config.get("env", None)
                    )
                    # Убеждаемся, что transport указан
                    if isinstance(stdio_config, dict):
                        stdio_config["transport"] = "stdio"
                    connections[server_name] = stdio_config
                
                if self.verbose:
                    print(f"Настройка MCP сервера: {server_name}")
            
            # Создаем клиент для работы с несколькими серверами
            if self.verbose:
                print(f"Подключение к {len(connections)} MCP серверам...")
            
            self.mcp_client = MultiServerMCPClient(connections=connections)
            
            # Получаем все инструменты
            tools = await self.mcp_client.get_tools()
            
            if self.verbose:
                print(f"✓ Загружено {len(tools)} инструментов из всех MCP серверов")
            
            return tools
        
        except Exception as e:
            print(f"Error: Не удалось загрузить инструменты из MCP серверов: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def initialize(self):
        """Инициализировать агента (загрузить инструменты)"""
        if self.verbose:
            print("Инициализация агента...")
        
        # Загружаем инструменты из MCP серверов
        self.tools = await self._load_mcp_tools()
        
        if not self.tools:
            print("Warning: Не загружено ни одного инструмента")
            return
        
        if self.verbose:
            print(f"Всего загружено инструментов: {len(self.tools)}")
        
        # Создаем ReAct агента через LangChain
        # langchain_create_agent возвращает граф, готовый к использованию
        # checkpointer передается как именованный аргумент после *
        try:
            agent_graph = langchain_create_agent(
                self.llm,
                self.tools,
                checkpointer=self.checkpointer
            )
            # Проверяем, что получили правильный объект
            if not hasattr(agent_graph, 'ainvoke'):
                raise ValueError(f"langchain_create_agent вернул объект без метода ainvoke: {type(agent_graph)}")
            self.agent_graph = agent_graph
        except TypeError as e:
            # Если checkpointer не поддерживается, пробуем без него
            if "checkpointer" in str(e).lower():
                if self.verbose:
                    print("Warning: checkpointer не поддерживается, создаем агента без него")
                agent_graph = langchain_create_agent(
                    self.llm,
                    self.tools
                )
                if not hasattr(agent_graph, 'ainvoke'):
                    raise ValueError(f"langchain_create_agent вернул объект без метода ainvoke: {type(agent_graph)}")
                self.agent_graph = agent_graph
            else:
                raise
        except Exception as e:
            if self.verbose:
                print(f"Error creating agent: {type(e).__name__}: {e}")
            raise
        
        if self.verbose:
            print("✓ Агент инициализирован")
    
    def _safe_extract_content(self, message) -> str:
        """Безопасное извлечение контента из сообщения с обработкой кодировки"""
        try:
            # Извлекаем контент
            if hasattr(message, "content"):
                content = message.content
            elif isinstance(message, dict):
                content = message.get("content", "")
            else:
                content = message
            
            # Обрабатываем None
            if content is None:
                return ""
            
            # Если это байты, декодируем
            if isinstance(content, bytes):
                try:
                    # Пробуем UTF-8
                    content = content.decode('utf-8', errors='replace')
                except Exception:
                    # Если не получилось, пробуем latin-1 (всегда работает)
                    try:
                        content = content.decode('latin-1', errors='replace')
                    except:
                        # Последняя попытка - просто заменяем проблемные байты
                        content = content.decode('utf-8', errors='replace')
            
            # Если это уже строка, просто возвращаем её
            # НЕ делаем двойное encode/decode - это может вызвать ошибки
            if isinstance(content, str):
                return content
            
            # Для других типов конвертируем в строку
            try:
                return str(content)
            except:
                return repr(content)
                
        except Exception as e:
            # В случае любой ошибки возвращаем безопасное сообщение
            try:
                # Безопасное получение сообщения об ошибке
                error_msg = None
                
                if hasattr(e, 'args') and e.args:
                    try:
                        error_msg = str(e.args[0])
                        if isinstance(error_msg, bytes):
                            error_msg = error_msg.decode('utf-8', errors='replace')
                    except:
                        pass
                
                if not error_msg:
                    try:
                        error_msg = repr(e)
                    except:
                        pass
                
                if not error_msg:
                    error_msg = "Ошибка при извлечении контента"
                    
                if not isinstance(error_msg, str):
                    error_msg = "Ошибка при извлечении контента"
                    
            except Exception:
                error_msg = "Ошибка при извлечении контента"
            
            return f"Ошибка при извлечении контента: {error_msg}"
    
    async def run(self, query: str) -> str:
        """
        Выполнить запрос через агента
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Ответ агента
        """
        if self.agent_graph is None:
            await self.initialize()
        
        if self.agent_graph is None:
            return "Ошибка: Агент не инициализирован"
        
        # Проверяем, что agent_graph имеет метод ainvoke
        if not hasattr(self.agent_graph, 'ainvoke'):
            return f"Ошибка: agent_graph не имеет метода ainvoke. Тип: {type(self.agent_graph)}"
        
        try:
            # LangGraph использует объекты сообщений
            config = {"configurable": {"thread_id": "1"}}
            result = await self.agent_graph.ainvoke(
                {"messages": [HumanMessage(content=query)]},
                config=config
            )
            
            # Извлекаем последнее сообщение агента
            if result.get("messages"):
                last_message = result["messages"][-1]
                try:
                    content = self._safe_extract_content(last_message)
                    if content and content.strip():
                        return content
                except Exception as extract_error:
                    # Если не удалось извлечь контент, пробуем другой способ
                    try:
                        if hasattr(last_message, "content"):
                            return str(last_message.content)
                        elif isinstance(last_message, dict):
                            return str(last_message.get("content", ""))
                        else:
                            return str(last_message)
                    except:
                        pass
            
            # Пробуем получить output
            output = result.get("output")
            if output:
                try:
                    return self._safe_extract_content(output)
                except:
                    return str(output)
            
            return "Нет ответа"
        except Exception as e:
            # Безопасная обработка ошибок с улучшенной обработкой кодировки
            error_msg = "Неизвестная ошибка"
            error_type = "Exception"
            
            try:
                error_type = type(e).__name__
                
                # Пробуем получить сообщение об ошибке с максимальной безопасностью
                if hasattr(e, 'args') and e.args:
                    try:
                        first_arg = e.args[0]
                        if isinstance(first_arg, bytes):
                            error_msg = first_arg.decode('utf-8', errors='replace')
                        elif isinstance(first_arg, str):
                            # Безопасно обрабатываем строку
                            error_msg = first_arg.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        else:
                            error_msg = str(first_arg).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                    except Exception as decode_err:
                        try:
                            error_msg = f"Ошибка в args[0]: {type(decode_err).__name__}"
                        except:
                            error_msg = "Ошибка при обработке args"
                
                # Если не получилось, пробуем str(e) с безопасной обработкой
                if error_msg == "Неизвестная ошибка":
                    try:
                        error_str = str(e)
                        if isinstance(error_str, bytes):
                            error_str = error_str.decode('utf-8', errors='replace')
                        else:
                            error_str = error_str.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        error_msg = error_str
                    except Exception as str_err:
                        try:
                            error_msg = f"Ошибка при str(e): {type(str_err).__name__}"
                        except:
                            pass
                
                # Если все еще не получилось, пробуем repr с ограничением
                if error_msg == "Неизвестная ошибка":
                    try:
                        error_repr = repr(e)
                        if isinstance(error_repr, bytes):
                            error_repr = error_repr.decode('utf-8', errors='replace')
                        error_repr = error_repr.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        error_msg = f"{error_type}: {error_repr[:300]}"
                    except:
                        error_msg = f"{error_type}: ошибка при обработке исключения"
                
                # Убеждаемся, что это строка
                if not isinstance(error_msg, str):
                    error_msg = f"{error_type}: ошибка при обработке исключения"
                
                # Ограничиваем длину сообщения
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "..."
                    
            except Exception:
                try:
                    error_msg = f"Ошибка ({error_type}) при обработке исключения"
                except:
                    error_msg = "Критическая ошибка при обработке исключения"
            
            return f"Ошибка при выполнении запроса ({error_type}): {error_msg}"
    
    def run_sync(self, query: str) -> str:
        """
        Синхронная версия run (для удобства)
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Ответ агента
        """
        return asyncio.run(self.run(query))
    
    async def close(self):
        """Закрыть соединения с MCP серверами"""
        if self.mcp_client and hasattr(self.mcp_client, 'close'):
            try:
                await self.mcp_client.close()
            except Exception as e:
                if self.verbose:
                    print(f"Warning: Ошибка при закрытии MCP клиента: {e}")


# Глобальный экземпляр агента
_design_agent: Optional[MultiMCPAgent] = None


async def get_agent() -> MultiMCPAgent:
    """Получить или создать глобальный экземпляр агента"""
    global _design_agent
    if _design_agent is None:
        _design_agent = MultiMCPAgent()
        await _design_agent.initialize()
    return _design_agent


def create_mcp_agent(
    llm: Optional[BaseChatModel] = None,
    mcp_servers: Optional[List[dict]] = None,
    verbose: bool = True
) -> MultiMCPAgent:
    """
    Создать новый экземпляр агента
    
    Args:
        llm: Языковая модель
        mcp_servers: Список конфигураций MCP серверов
        verbose: Выводить ли подробную информацию
        
    Returns:
        Экземпляр MultiMCPAgent
    """
    agent = MultiMCPAgent(llm=llm, mcp_servers=mcp_servers, verbose=verbose)
    return agent


async def chat_mode(agent: MultiMCPAgent):
    """Интерактивный режим чата с агентом"""
    print("\n" + "="*60)
    print("🤖 Интерактивный чат с агентом")
    print("="*60)
    print("Введите ваш запрос (или 'exit'/'quit' для выхода, 'clear' для очистки истории)")
    print("="*60 + "\n")
    
    while True:
        try:
            # Получаем запрос от пользователя
            query = input("Вы: ").strip()
            
            # Проверяем команды выхода
            if query.lower() in ['exit', 'quit', 'выход']:
                print("\n👋 До свидания!")
                break
            
            # Очистка экрана (просто пропуск)
            if query.lower() in ['clear', 'очистить']:
                print("\n" * 2)
                continue
            
            # Пропускаем пустые запросы
            if not query:
                continue
            
            # Выполняем запрос
            print("\n🤔 Думаю...\n")
            response = await agent.run(query)
            
            # Безопасный вывод ответа с обработкой кодировки
            try:
                # Убеждаемся, что response - это строка
                if not isinstance(response, str):
                    response = str(response)
                
                # Заменяем проблемные символы, если они есть
                safe_response = response.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                
                print(f"\n🤖 Агент: {safe_response}\n")
                print("-" * 60 + "\n")
            except Exception as print_error:
                # Если даже вывод не работает, пробуем через repr
                try:
                    safe_response = repr(response)[:500]
                    print(f"\n🤖 Агент (raw): {safe_response}\n")
                    print("-" * 60 + "\n")
                except:
                    print("\n🤖 Агент: [Ошибка при выводе ответа]\n")
                    print("-" * 60 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Прервано пользователем. До свидания!")
            break
        except Exception as e:
            # Безопасный вывод ошибки с улучшенной обработкой кодировки
            error_msg = "Неизвестная ошибка"
            error_type = "Exception"
            
            try:
                error_type = type(e).__name__
                
                # Пробуем получить сообщение об ошибке с максимальной безопасностью
                if hasattr(e, 'args') and e.args:
                    try:
                        first_arg = e.args[0]
                        if isinstance(first_arg, bytes):
                            error_msg = first_arg.decode('utf-8', errors='replace')
                        elif isinstance(first_arg, str):
                            # Безопасно обрабатываем строку
                            error_msg = first_arg.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        else:
                            error_msg = str(first_arg).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                    except Exception as decode_err:
                        try:
                            error_msg = f"Ошибка в args[0]: {type(decode_err).__name__}"
                        except:
                            error_msg = "Ошибка при обработке args"
                
                # Если не получилось, пробуем str(e) с безопасной обработкой
                if error_msg == "Неизвестная ошибка":
                    try:
                        error_str = str(e)
                        if isinstance(error_str, bytes):
                            error_str = error_str.decode('utf-8', errors='replace')
                        else:
                            error_str = error_str.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        error_msg = error_str
                    except Exception as str_err:
                        try:
                            error_msg = f"Ошибка при str(e): {type(str_err).__name__}"
                        except:
                            pass
                
                # Если все еще не получилось, пробуем repr с ограничением
                if error_msg == "Неизвестная ошибка":
                    try:
                        error_repr = repr(e)
                        if isinstance(error_repr, bytes):
                            error_repr = error_repr.decode('utf-8', errors='replace')
                        error_repr = error_repr.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        error_msg = f"{error_type}: {error_repr[:300]}"
                    except:
                        error_msg = f"{error_type}: ошибка при обработке исключения"
                
                # Убеждаемся, что это строка
                if not isinstance(error_msg, str):
                    error_msg = f"{error_type}: ошибка при обработке исключения"
                
                # Ограничиваем длину сообщения
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "..."
                    
            except Exception as inner_e:
                # Если даже обработка ошибки не удалась
                try:
                    error_msg = f"Ошибка ({error_type}) при обработке исключения: {type(inner_e).__name__}"
                except:
                    error_msg = "Критическая ошибка при обработке исключения"
            
            # Безопасный вывод ошибки
            try:
                print(f"\n❌ Ошибка ({error_type}): {error_msg}\n")
                print("-" * 60 + "\n")
            except Exception:
                # Если даже print не работает, пробуем через sys.stderr
                import sys
                try:
                    sys.stderr.write(f"\n❌ Ошибка ({error_type}): {error_msg}\n\n")
                    sys.stderr.write("-" * 60 + "\n\n")
                except:
                    pass


# Пример использования
if __name__ == "__main__":
    import sys
    
    async def main():
        # Создаем агента
        agent = create_mcp_agent(verbose=True)
        
        # Инициализируем
        print("Инициализация агента...")
        await agent.initialize()
        print("✓ Агент готов к работе!\n")
        
        # Проверяем аргументы командной строки
        if len(sys.argv) > 1:
            # Режим с аргументами - выполняем запросы из командной строки
            for query in sys.argv[1:]:
                print(f"\n{'='*60}")
                print(f"Запрос: {query}")
                print(f"{'='*60}")
                response = await agent.run(query)
                print(f"\nОтвет:\n{response}\n")
        else:
            # Интерактивный режим чата
            await chat_mode(agent)
    
    # Запускаем
    asyncio.run(main())
