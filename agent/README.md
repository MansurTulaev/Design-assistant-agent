# LangChain Agent для работы с несколькими MCP серверами

Агент на базе LangChain, который может использовать инструменты из нескольких MCP (Model Context Protocol) серверов одновременно.

## Быстрый старт

### 1. Установка зависимостей

```bash
cd agent
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта или экспортируйте переменные:

```bash
# Выберите один из провайдеров LLM:

# OpenAI
export OPENAI_API_KEY=your_openai_api_key
export OPENAI_MODEL=gpt-4o-mini  # опционально

# Или Anthropic
export ANTHROPIC_API_KEY=your_anthropic_api_key

# Или Ollama (локальный)
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.2
```

### 3. Запуск агента

#### Вариант 1: Прямой запуск (с примерами)

```bash
cd agent
python main.py
```

#### Вариант 2: Использование в своем коде

```python
import asyncio
from agent.main import create_agent

async def main():
    agent = create_agent(verbose=True)
    await agent.initialize()
    response = await agent.run("Найди популярные UI библиотеки для React")
    print(response)

asyncio.run(main())
```

### 4. Запуск MCP сервера (если нужно)

Агент автоматически найдет MCP сервер в `../mcp_rag/main.py`, но если вы хотите запустить его отдельно:

```bash
# Локально
cd mcp_rag
python main.py

# Или через Docker (все сервисы)
cd ..
docker-compose up -d
```

## Настройка

Создайте файл `.env` в корне проекта или установите переменные окружения:

```bash
# Выберите один из провайдеров LLM:

# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini  # опционально

# Anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022  # опционально

# Ollama (локальный)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2  # опционально
```

## Использование

### Базовый пример

```python
import asyncio
from agent.main import create_agent

async def main():
    # Создаем агента (автоматически найдет MCP серверы)
    agent = create_agent(verbose=True)
    
    # Инициализируем
    await agent.initialize()
    
    # Выполняем запрос
    response = await agent.run("Найди популярные UI библиотеки для React")
    print(response)

asyncio.run(main())
```

### Синхронное использование

```python
from agent.main import create_agent

agent = create_agent(verbose=True)
agent.run_sync("Найди информацию о пакете @mui/material")
```

### Настройка нескольких MCP серверов

```python
from agent.main import create_agent
from langchain_openai import ChatOpenAI

# Настраиваем MCP серверы
mcp_servers = [
    {
        "name": "mcp_rag",
        "command": "python",
        "args": ["/path/to/mcp_rag/main.py"]
    },
    {
        "name": "another_server",
        "command": "node",
        "args": ["/path/to/another/server.js"]
    },
    # HTTP сервер
    {
        "name": "http_server",
        "url": "http://localhost:8000/mcp"
    }
]

# Создаем агента с кастомной LLM и серверами
llm = ChatOpenAI(model="gpt-4", temperature=0)
agent = create_agent(llm=llm, mcp_servers=mcp_servers, verbose=True)

await agent.initialize()
response = await agent.run("Ваш запрос")
```

## Структура

- `main.py` - основной файл с классом `MultiMCPAgent`
- `requirements.txt` - зависимости проекта

## Класс MultiMCPAgent

### Методы

- `initialize()` - инициализирует агента и загружает инструменты из MCP серверов
- `run(query: str)` - асинхронно выполняет запрос
- `run_sync(query: str)` - синхронно выполняет запрос

### Параметры конструктора

- `llm` - языковая модель (если None, выбирается из env переменных)
- `mcp_servers` - список конфигураций MCP серверов
- `verbose` - выводить ли подробную информацию

## Конфигурация MCP серверов

### Stdio транспорт (локальные серверы)

```python
{
    "name": "server_name",
    "command": "python",  # или "node", "go", и т.д.
    "args": ["path/to/server.py"],
    "env": {"KEY": "value"}  # опционально
}
```

### HTTP транспорт (удаленные серверы)

```python
{
    "name": "server_name",
    "url": "http://localhost:8000/mcp"
}
```

## Примеры запросов

```python
# Поиск UI библиотек
await agent.run("Найди популярные UI библиотеки для React с компонентами кнопок")

# Информация о пакете
await agent.run("Получи информацию о пакете @mui/material")

# Семантический поиск в RAG
await agent.run("Найди компоненты для форм в RAG базе")

# Комплексный запрос
await agent.run("Найди UI библиотеку с компонентами таблиц, получи её README и проиндексируй в RAG")
```

## Требования

- Python 3.11+
- Установленные MCP серверы
- Один из LLM провайдеров (OpenAI, Anthropic, или Ollama)

