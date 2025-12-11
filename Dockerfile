FROM python:3.12-slim

WORKDIR /app

# Копируем зависимости
COPY pyproject.toml ./

# Устанавливаем зависимости
RUN pip install --no-cache-dir -e .

# Копируем исходный код
COPY src/ ./src/
COPY agent-config/ ./agent-config/

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 agentuser && chown -R agentuser:agentuser /app
USER agentuser

# Точка входа
CMD ["python", "-m", "src.start_a2a"]