import os
import logging

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard
from dotenv import load_dotenv

from src.agent_task_manager import MyAgentExecutor
from phoenix.otel import register

# Настройка логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Загружаем переменные окружения
        load_dotenv()
        
        # Настройка Phoenix для трассировки
        if os.getenv('ENABLE_PHOENIX', 'false').lower() == 'true':
            register(
                project_name=os.getenv("AGENT_NAME", "Figma-React-Agent"),
                endpoint=os.getenv("PHOENIX_ENDPOINT"),
                auto_instrument=True
            )

        # Создаём экземпляр исполнителя
        my_agent_executor = MyAgentExecutor()
        
        # Карточка агента для UI
        agent_card = AgentCard(
            name=os.getenv('AGENT_NAME', 'Figma to React Agent'),
            description=os.getenv('AGENT_DESCRIPTION', 
                                 'Generates React/TSX components from Figma designs using your design system'),
            url=os.getenv('URL_AGENT', ''),
            version=os.getenv('AGENT_VERSION', '1.0.0'),
            default_input_modes=my_agent_executor.agent.SUPPORTED_CONTENT_TYPES,
            default_output_modes=my_agent_executor.agent.SUPPORTED_CONTENT_TYPES,
            capabilities=AgentCapabilities(streaming=True),
            skills=["react", "typescript", "figma", "design-systems"],
        )
        
        # Обработчик запросов
        request_handler = DefaultRequestHandler(
            agent_executor=my_agent_executor,
            task_store=InMemoryTaskStore(),
        )
        
        # Запускаем сервер
        server = A2AStarletteApplication(
            agent_card=agent_card, 
            http_handler=request_handler
        )
        
        import uvicorn
        uvicorn.run(
            server.build(), 
            host='0.0.0.0', 
            port=int(os.getenv("PORT", 10000)),
            log_level="info"
        )
        
    except Exception as e:
        logger.error(f'Failed to start server: {e}')
        raise

if __name__ == '__main__':
    main()