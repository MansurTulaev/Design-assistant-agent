# MCP RAG Project

LangChain агент для работы с UI компонентами из NPM через MCP (Model Context Protocol) с поддержкой RAG (Retrieval-Augmented Generation).

## 🚀 Запуск

### Docker (рекомендуется)

```bash
# 1. Создайте .env файл (см. env.example)
cp env.example .env

# 2. Запустите все сервисы
docker-compose up -d

# 3. Запустите агента в интерактивном режиме
./chat.sh
```

### Локально

```bash
# 1. Установите зависимости
pip install -r requirements.txt
pip install -r agent/requirements.txt
pip install -r mcp_rag/requirements.txt

# 2. Настройте переменные окружения
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.2
export QDRANT_URL=http://localhost:6333
export REDIS_HOST=localhost
export REDIS_PORT=6379

# 3. Запустите сервисы (Qdrant, Redis, Ollama)
docker-compose up -d qdrant redis ollama

# 4. Скачайте модель Ollama (если нужно)
docker-compose exec ollama ollama pull llama3.2

# 5. Запустите агента
cd agent && python main.py
```

## 📁 Структура проекта

```
mcp_rag-1/
├── agent/                    # LangChain агент
│   ├── main.py              # MultiMCPAgent - основной класс агента
│   ├── requirements.txt     # Зависимости агента
│   └── README.md            # Документация агента
│
├── mcp_rag/                 # MCP сервер (FastMCP)
│   ├── main.py              # FastMCP сервер с инструментами
│   ├── npm_registry.py      # Клиент NPM Registry API
│   ├── rag_service.py       # Сервис для работы с Qdrant (RAG)
│   ├── cache_service.py     # Сервис кэширования (Redis)
│   ├── storybook_parser.py  # Парсер компонентов из Storybook
│   ├── requirements.txt     # Зависимости MCP сервера
│   └── README.md            # Документация MCP сервера
│
├── schemas/                 # JSON схемы для компонентов
│   └── schemas.json
│
├── Dockerfile               # Единый Docker образ (агент + MCP)
├── docker-compose.yaml      # Docker Compose конфигурация
├── docker-entrypoint.sh     # Entrypoint скрипт для контейнера
├── chat.sh                  # Скрипт для запуска чата
├── requirements.txt         # Общие зависимости
└── env.example              # Пример файла с переменными окружения
```

## 🛠️ Инструменты (Tools)

### Работа с NPM

- **`search_npm_packages`** - Поиск пакетов в NPM Registry по ключевым словам
- **`get_npm_package_info`** - Получить подробную информацию о NPM пакете
- **`get_npm_component_data`** - Получить данные о компонентах из NPM пакета
- **`get_npm_readme`** - Получить README файл из NPM пакета
- **`search_ui_libraries`** - Поиск UI библиотек (Material-UI, Ant Design, Chakra UI, Kontur UI и др.)

### Работа со Storybook

- **`parse_storybook_url`** - Парсинг компонентов из Storybook URL
- **`index_storybook_to_rag`** - Индексация компонентов из Storybook в RAG

### RAG (векторный поиск)

- **`index_npm_package_to_rag`** - Индексировать компоненты из NPM пакета в Qdrant
- **`search_components_rag`** - Семантический поиск компонентов в RAG
- **`get_rag_collection_stats`** - Получить статистику коллекции в RAG

### Поддерживаемые UI библиотеки

- Material-UI (@mui/material)
- Ant Design (antd)
- Chakra UI (@chakra-ui/react)
- Radix UI (@radix-ui/react-*)
- Headless UI (@headlessui/react)
- Mantine (@mantine/core)
- React Bootstrap
- Semantic UI React
- **Kontur UI (@skbkontur/react-ui)**
