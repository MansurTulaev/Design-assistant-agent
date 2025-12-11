#!/bin/bash
# Скрипт для запуска интерактивного чата с агентом

cd "$(dirname "$0")"

echo "🚀 Запуск интерактивного чата с агентом..."
echo ""

# Убеждаемся, что MCP сервер запущен
if ! docker ps | grep -q mcp_rag_background; then
    echo "📡 Запуск MCP сервера в фоне..."
    docker-compose run -d --name mcp_rag_background --rm -e RUN_MODE=mcp agent > /dev/null 2>&1
    sleep 3
fi

# Запускаем агента в интерактивном режиме
echo "🤖 Подключение к агенту..."
echo ""
docker-compose run --rm -e RUN_MODE=agent agent python /app/agent/main.py

