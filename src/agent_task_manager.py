from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Task, TaskState, UnsupportedOperationError
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from src.a2a_agent import A2Aagent

class MyAgentExecutor(AgentExecutor):
    """Executor для Figma-React агента"""
    
    def __init__(self):
        self.agent = A2Aagent()
        self.logger = logging.getLogger(__name__)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = context.get_user_input()
        task = context.current_task
        self.logger.info(f"Processing query: {query[:100]}...")

        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
            
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        
        try:
            async for item in self.agent.stream(query, task.context_id):
                is_task_complete = item['is_task_complete']
                require_user_input = item['require_user_input']
                is_error = item['is_error']
                is_event = item['is_event']

                if is_error:
                    await updater.update_status(
                        TaskState.failed,
                        new_agent_text_message(
                            item['content'], task.context_id, task.id
                        ),
                    )
                    break
                    
                if is_event:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item['content'], task.context_id, task.id
                        ),
                    )
                    continue
                    
                if not is_task_complete and not require_user_input:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item['content'], task.context_id, task.id
                        ),
                    )
                    continue

                if not is_task_complete and require_user_input:
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            item['content'], task.context_id, task.id
                        ),
                    )
                    break
                    
                if is_task_complete and not require_user_input:
                    await updater.update_status(
                        TaskState.completed,
                        new_agent_text_message(
                            item['content'], task.context_id, task.id
                        ),
                    )
                    break
                    
        except Exception as e:
            self.logger.error(f"Agent execution failed: {e}")
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(
                    f"Error: {str(e)}", task.context_id, task.id
                ),
            )

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())