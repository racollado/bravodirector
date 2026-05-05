"""
Task Manager — tracks background generation tasks by ID, stores outputs, supports awaiting.

Each long-running generation (music, video, TTS) is registered as a task with a unique ID.
Other parts of the system can await tasks or poll their status. Task outputs (file paths,
generated text) are stored for later reference via the $task_id syntax in the script.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    output: Any = None
    error: Optional[str] = None
    progress: float = 0.0
    _future: Optional[asyncio.Task] = field(default=None, repr=False)


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, TaskInfo] = {}

    def register(self, task_id: str, coro, loop: asyncio.AbstractEventLoop) -> TaskInfo:
        """Register and start a background task."""
        info = TaskInfo(task_id=task_id, status=TaskStatus.RUNNING)

        async def _wrapper():
            try:
                result = await coro
                info.output = result
                info.status = TaskStatus.COMPLETED
                info.progress = 1.0
                logger.info("Task '%s' completed successfully", task_id)
            except asyncio.CancelledError:
                info.status = TaskStatus.FAILED
                info.error = "Cancelled"
                logger.warning("Task '%s' was cancelled", task_id)
            except Exception as e:
                info.status = TaskStatus.FAILED
                info.error = str(e)
                logger.error("Task '%s' failed: %s", task_id, e)

        info._future = asyncio.run_coroutine_threadsafe(_wrapper(), loop)
        self._tasks[task_id] = info
        logger.info("Task '%s' registered and started", task_id)
        return info

    def register_with_async_task(self, task_id: str, async_task: asyncio.Task) -> TaskInfo:
        """Register an already-created asyncio.Task."""
        info = TaskInfo(task_id=task_id, status=TaskStatus.RUNNING)
        info._future = async_task
        self._tasks[task_id] = info
        return info

    def get(self, task_id: str) -> Optional[TaskInfo]:
        return self._tasks.get(task_id)

    def get_output(self, task_id: str) -> Any:
        info = self._tasks.get(task_id)
        if info and info.status == TaskStatus.COMPLETED:
            return info.output
        return None

    def resolve_reference(self, ref: str) -> Any:
        """Resolve a $task_id reference to its output."""
        if isinstance(ref, str) and ref.startswith("$"):
            task_id = ref[1:]
            output = self.get_output(task_id)
            if output is None:
                logger.warning("Task reference '%s' not resolved (task not completed)", ref)
            return output
        return ref

    async def wait_for(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """Await a task's completion. Returns the output."""
        info = self._tasks.get(task_id)
        if not info:
            logger.warning("Cannot wait for unknown task '%s'", task_id)
            return None

        if info.status == TaskStatus.COMPLETED:
            return info.output

        if info._future is None:
            return None

        try:
            if isinstance(info._future, asyncio.Task):
                await asyncio.wait_for(info._future, timeout=timeout)
            else:
                await asyncio.wait_for(
                    asyncio.wrap_future(info._future),
                    timeout=timeout,
                )
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for task '%s'", task_id)
        except Exception as e:
            logger.error("Error waiting for task '%s': %s", task_id, e)

        return info.output

    def set_progress(self, task_id: str, progress: float):
        info = self._tasks.get(task_id)
        if info:
            info.progress = min(1.0, max(0.0, progress))

    def complete(self, task_id: str, output: Any):
        """Manually mark a task as completed with the given output."""
        info = self._tasks.get(task_id)
        if info:
            info.output = output
            info.status = TaskStatus.COMPLETED
            info.progress = 1.0
            logger.info("Task '%s' manually completed", task_id)
        else:
            info = TaskInfo(task_id=task_id, status=TaskStatus.COMPLETED, output=output, progress=1.0)
            self._tasks[task_id] = info

    def cancel(self, task_id: str):
        info = self._tasks.get(task_id)
        if info and info._future and not info._future.done():
            if isinstance(info._future, asyncio.Task):
                info._future.cancel()
            info.status = TaskStatus.FAILED
            info.error = "Cancelled"

    def cancel_all(self):
        for task_id in list(self._tasks.keys()):
            self.cancel(task_id)

    def clear(self):
        self.cancel_all()
        self._tasks.clear()

    # ------------------------------------------------------------------
    # Serialization for WebSocket
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            tid: {
                "task_id": info.task_id,
                "status": info.status.value,
                "progress": info.progress,
                "error": info.error,
                "has_output": info.output is not None,
            }
            for tid, info in self._tasks.items()
        }
