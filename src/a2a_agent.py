from typing import Dict, Any, AsyncGenerator
import asyncio
import logging

from google.genai import types
from google.adk import Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService, Session

from src.agent import worker_agent

logger = logging.getLogger("figma_react_agent")

class A2Aagent:
    def __init__(self):
        self.agent = worker_agent
        self.runner = Runner(
            app_name=self.agent.name,
            agent=self.agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
            credential_service=InMemoryCredentialService()
        )

    async def get_session(self, session_id) -> Session:
        """Получает или создает сессию для пользователя"""
        session = await self.runner.session_service.get_session(
            app_name=self.agent.name,
            user_id='a2a_user',
            session_id=session_id
        )

        if session is None:
            session = await self.runner.session_service.create_session(
                app_name=self.agent.name,
                user_id='a2a_user',
                session_id=session_id
            )

        return session

    async def invoke(self, query: str, session_id: str) -> Dict[str, Any]:
        """Синхронный вызов агента"""
        session = await self.get_session(session_id)

        content = types.Content(
            role='user',
            parts=[types.Part.from_text(text=query)],
        )
        
        last_event = None
        async for event in self.runner.run_async(
                user_id=session.user_id, session_id=session.id, new_message=content
        ):
            last_event = event

        response = '\n'.join(p.text for p in last_event.content.parts if p.text)

        return {
            "is_task_complete": True,
            "require_user_input": False,
            "content": response,
            "is_error": False,
            "is_event": False
        }

    async def stream(self, query: str, session_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Стриминговый вызов агента"""
        session = await self.get_session(session_id)

        content = types.Content(
            role='user',
            parts=[types.Part.from_text(text=query)],
        )
        
        last_event = None
        async for event in self.runner.run_async(
                user_id=session.user_id, session_id=session.id, new_message=content
        ):
            # Отправляем промежуточные статусы
            for part in event.content.parts:
                if part.function_call is not None:
                    # Логируем вызовы инструментов
                    if 'action' in part.function_call.args:
                        yield {
                            "is_task_complete": False,
                            "require_user_input": False,
                            "content": f"🔄 {part.function_call.args.get('action', 'Processing...')}",
                            "is_error": False,
                            "is_event": True
                        }
            
            last_event = event

        # Финальный ответ
        if last_event and last_event.content.parts:
            response = '\n'.join(p.text for p in last_event.content.parts if p.text)
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": response,
                "is_error": False,
                "is_event": False
            }

    # Для совместимости
    def sync_invoke(self, query: str, session_id: str) -> Dict[str, Any]:
        return asyncio.run(self.invoke(query, session_id))

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]