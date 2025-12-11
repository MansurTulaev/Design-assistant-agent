#!/bin/bash
set -e

# Устанавливаем переменные окружения для временных директорий
export TMPDIR=${TMPDIR:-/tmp}
export TEMP=${TEMP:-/tmp}
export TMP=${TMP:-/tmp}

# Создаем временные директории, если их нет, с принудительной проверкой
if [ ! -d /tmp ]; then
    mkdir -p /tmp
fi
if [ ! -d /var/tmp ]; then
    mkdir -p /var/tmp
fi
if [ ! -d /usr/tmp ]; then
    mkdir -p /usr/tmp
fi

# Устанавливаем права доступа
chmod 1777 /tmp /var/tmp /usr/tmp 2>/dev/null || true

# Проверяем, что директории доступны для записи
if [ ! -w /tmp ]; then
    echo "Warning: /tmp не доступен для записи"
fi

# Определяем режим запуска
MODE=${RUN_MODE:-both}

echo "=========================================="
echo "MCP RAG Project - Docker Entrypoint"
echo "Режим запуска: $MODE"
echo "=========================================="

case "$MODE" in
  agent)
    echo "Запуск только агента..."
    echo "Убедитесь, что MCP сервер запущен отдельно"
    cd /app/agent
    exec python main.py
    ;;
    
  mcp)
    echo "Запуск только MCP сервера..."
    cd /app/mcp_rag
    exec python main.py
    ;;
    
  both)
    echo "Запуск MCP сервера в фоне..."
    
    # Убеждаемся, что временные директории доступны перед запуском MCP
    export TMPDIR=/tmp
    export TEMP=/tmp
    export TMP=/tmp
    mkdir -p /tmp /var/tmp /usr/tmp
    chmod 1777 /tmp /var/tmp /usr/tmp 2>/dev/null || true
    
    cd /app/mcp_rag
    # Запускаем MCP сервер с явно установленными переменными окружения
    TMPDIR=/tmp TEMP=/tmp TMP=/tmp python main.py &
    MCP_PID=$!
    echo "MCP сервер запущен (PID: $MCP_PID)"
    
    # Ждем немного, чтобы сервер успел запуститься
    sleep 3
    
    # Проверяем, что MCP сервер еще работает
    if ! kill -0 $MCP_PID 2>/dev/null; then
        echo "Warning: MCP сервер завершился. Проверьте логи."
    fi
    
    echo "Запуск агента..."
    cd /app/agent
    exec python main.py
    ;;
    
  *)
    echo "Ошибка: Неизвестный режим: $MODE"
    echo "Доступные режимы:"
    echo "  - agent  : только агент"
    echo "  - mcp    : только MCP сервер"
    echo "  - both   : агент + MCP сервер (по умолчанию)"
    exit 1
    ;;
esac

