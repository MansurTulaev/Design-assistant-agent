from __future__ import annotations
import os

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import SseConnectionParams, McpToolset
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем системный промпт из файла для лучшей читаемости
def get_system_prompt():
    """Загружает системный промпт из файла"""
    prompt_path = os.getenv('AGENT_SYSTEM_PROMPT_FILE', './agent-config/system-prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        # Fallback на переменную окружения
        return os.getenv("AGENT_SYSTEM_PROMPT", "")

# Конфигурация LLM (Qwen или другая модель)
llm_model = LiteLlm(
    model=os.getenv("LLM_MODEL", "hosted_vllm/Qwen/Qwen3-Coder-480B-A35B-Instruct"),
    api_base=os.getenv("LLM_API_BASE", "https://foundation-models.api.cloud.ru/v1"),
    api_key=os.getenv("LLM_API_KEY", "")
)

# Получаем список MCP серверов
mcp_urls = os.getenv("MCP_URL", "").split(',')
mcp_tools = []
for url in mcp_urls:
    if url.strip():  # Пропускаем пустые URL
        mcp_tools.append(
            McpToolset(
                connection_params=SseConnectionParams(url=url.strip())
            )
        )

# Создаём основного агента
worker_agent = Agent(
    model=llm_model,
    name=os.getenv('AGENT_NAME', 'Figma-React-Agent').replace(" ", '_'),
    description=os.getenv('AGENT_DESCRIPTION', 'Generates React components from Figma designs'),
    instruction=get_system_prompt(),  # Используем загруженный промпт
    tools=mcp_tools,
    # Включаем автоматическое использование инструментов
    handoff_description="I can use Figma and design system tools to generate React code"
)

root_agent = worker_agent