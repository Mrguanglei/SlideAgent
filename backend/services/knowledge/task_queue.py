"""
知识库任务队列管理器

功能：
- 管理文档解析任务的队列
- 控制并发处理数量
- 支持任务优先级
- 任务状态跟踪
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"       # 等待中
    QUEUED = "queued"         # 已入队
    PROCESSING = "processing" # 处理中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2


@dataclass
class Task:
    """任务对象"""
    id: str                              # 任务 ID（通常是 document_id）
    document_id: int                     # 文档 ID
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class DocumentTaskQueue:
    """文档处理任务队列"""
    
    _instance: Optional["DocumentTaskQueue"] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # 任务队列（按优先级分组）
        self._queues: Dict[TaskPriority, deque] = {
            TaskPriority.HIGH: deque(),
            TaskPriority.NORMAL: deque(),
            TaskPriority.LOW: deque(),
        }
        
        # 任务状态跟踪
        self._tasks: Dict[str, Task] = {}
        
        # 正在处理的任务
        self._processing: Dict[str, Task] = {}
        
        # 并发控制
        self._max_concurrent = 3  # 最大并发处理数
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        
        # 处理器函数
        self._processor: Optional[Callable] = None
        
        # 工作线程
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 锁
        self._lock = asyncio.Lock()
        
        logger.info(f"DocumentTaskQueue initialized with max_concurrent={self._max_concurrent}")
    
    def set_processor(self, processor: Callable):
        """设置任务处理器函数"""
        self._processor = processor
    
    async def start(self):
        """启动队列处理"""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("DocumentTaskQueue worker started")
    
    async def stop(self):
        """停止队列处理"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("DocumentTaskQueue worker stopped")
    
    async def add_task(
        self, 
        document_id: int, 
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> Task:
        """
        添加任务到队列
        
        Args:
            document_id: 文档 ID
            priority: 任务优先级
            
        Returns:
            创建的任务对象
        """
        task_id = f"doc_{document_id}"
        
        async with self._lock:
            # 检查是否已存在
            if task_id in self._tasks:
                existing = self._tasks[task_id]
                # 如果任务正在处理或已完成，不重复添加
                if existing.status in [TaskStatus.PROCESSING, TaskStatus.COMPLETED]:
                    logger.info(f"Task {task_id} already exists with status {existing.status}")
                    return existing
                # 如果任务失败或等待中，可以重新入队
                if existing.status == TaskStatus.FAILED:
                    existing.status = TaskStatus.QUEUED
                    existing.retry_count += 1
                    existing.error = None
                    self._queues[priority].append(task_id)
                    logger.info(f"Task {task_id} re-queued (retry {existing.retry_count})")
                    return existing
            
            # 创建新任务
            task = Task(
                id=task_id,
                document_id=document_id,
                priority=priority,
                status=TaskStatus.QUEUED,
            )
            
            self._tasks[task_id] = task
            self._queues[priority].append(task_id)
            
            logger.info(f"Task {task_id} added to queue with priority {priority.name}")
            
            return task
    
    async def add_tasks(
        self, 
        document_ids: List[int], 
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> List[Task]:
        """批量添加任务"""
        tasks = []
        for doc_id in document_ids:
            task = await self.add_task(doc_id, priority)
            tasks.append(task)
        return tasks
    
    def get_task(self, document_id: int) -> Optional[Task]:
        """获取任务状态"""
        task_id = f"doc_{document_id}"
        return self._tasks.get(task_id)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "pending": sum(len(q) for q in self._queues.values()),
            "processing": len(self._processing),
            "total_tasks": len(self._tasks),
            "max_concurrent": self._max_concurrent,
            "queues": {
                p.name: len(q) for p, q in self._queues.items()
            },
            "processing_tasks": list(self._processing.keys()),
        }
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有任务状态"""
        return [
            {
                "id": task.id,
                "document_id": task.document_id,
                "status": task.status.value,
                "priority": task.priority.name,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error": task.error,
                "retry_count": task.retry_count,
            }
            for task in self._tasks.values()
        ]
    
    async def _worker_loop(self):
        """工作循环"""
        while self._running:
            try:
                # 获取下一个任务
                task = await self._get_next_task()
                
                if task is None:
                    # 没有任务，等待一会儿
                    await asyncio.sleep(0.5)
                    continue
                
                # 使用信号量控制并发
                async with self._semaphore:
                    await self._process_task(task)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(1)
    
    async def _get_next_task(self) -> Optional[Task]:
        """获取下一个待处理的任务（按优先级）"""
        async with self._lock:
            # 按优先级顺序检查队列
            for priority in [TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW]:
                queue = self._queues[priority]
                while queue:
                    task_id = queue.popleft()
                    task = self._tasks.get(task_id)
                    
                    if task and task.status == TaskStatus.QUEUED:
                        task.status = TaskStatus.PROCESSING
                        task.started_at = datetime.utcnow()
                        self._processing[task_id] = task
                        return task
            
            return None
    
    async def _process_task(self, task: Task):
        """处理单个任务"""
        try:
            logger.info(f"Processing task {task.id}")
            
            if self._processor:
                await self._processor(task.document_id)
            
            # 标记完成
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            logger.info(f"Task {task.id} completed")
            
        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            
            # 检查是否需要重试
            if task.retry_count < task.max_retries:
                logger.info(f"Task {task.id} will be retried")
                await self.add_task(task.document_id, task.priority)
        
        finally:
            # 从处理中移除
            async with self._lock:
                self._processing.pop(task.id, None)


# 全局任务队列实例
task_queue = DocumentTaskQueue()


async def init_task_queue(processor: Callable):
    """初始化并启动任务队列"""
    task_queue.set_processor(processor)
    await task_queue.start()


async def shutdown_task_queue():
    """关闭任务队列"""
    await task_queue.stop()
