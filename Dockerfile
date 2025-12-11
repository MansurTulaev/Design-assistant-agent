FROM python:3.11-slim

WORKDIR /app

# Создаем временные директории для работы приложений
RUN mkdir -p /tmp /var/tmp /usr/tmp && \
    chmod 1777 /tmp /var/tmp /usr/tmp

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
COPY agent/requirements.txt agent-requirements.txt
COPY mcp_rag/requirements.txt mcp-requirements.txt

# Объединяем и устанавливаем все зависимости
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r agent-requirements.txt && \
    pip install --no-cache-dir -r mcp-requirements.txt

# Копируем entrypoint скрипт
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Копируем весь проект
COPY . .

ENTRYPOINT ["/entrypoint.sh"]

