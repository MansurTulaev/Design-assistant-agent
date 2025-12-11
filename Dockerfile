# Используем официальный образ Python 3.13 slim для минимального размера
FROM python:3.13-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости и uv в одном слое для оптимизации
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# Создаем файл README.md (чтобы избежать ошибки сборки)
RUN echo "# MCP Figma Kontur UI Scanner" > README.md && \
    echo "" >> README.md && \
    echo "MCP сервер для сканирования Figma дизайн-системы Kontur UI и генерации React кода на основе макетов." >> README.md

# Копируем файлы конфигурации uv сначала для лучшего кеширования Docker слоев
COPY pyproject.toml ./

# Создаем виртуальное окружение и устанавливаем зависимости
RUN uv sync --no-editable

# Копируем исходный код приложения
COPY src/ ./src/

# Создаем непривилегированного пользователя для безопасности
RUN useradd --create-home --shell /bin/bash --uid 1000 mcp && \
    chown -R mcp:mcp /app

# Переключаемся на непривилегированного пользователя
USER mcp

# Открываем порт для MCP сервера
EXPOSE 8000

# Устанавливаем переменные окружения для оптимальной работы Python
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    UV_SYSTEM_PYTHON=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Команда запуска сервера
CMD ["uv", "run", "python", "src/server.py"]