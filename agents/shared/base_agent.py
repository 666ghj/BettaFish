#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base Agent Class
Template for all BettaFish agents following multi-agent architecture
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from abc import ABC, abstractmethod
from loguru import logger


class AgentState(Enum):
    """Agent lifecycle states"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    READY = "ready"
    WORKING = "working"
    PAUSED = "paused"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class BaseAgent(ABC):
    """
    Base class for all BettaFish agents

    Provides:
    - Standard lifecycle management
    - Message bus communication
    - Health monitoring
    - Error handling
    - Metrics collection
    """

    def __init__(self, agent_name: str, config: Dict[str, Any]):
        """
        Initialize base agent

        Args:
            agent_name: Unique name for this agent
            config: Configuration dictionary
        """
        self.agent_name = agent_name
        self.config = config
        self.state = AgentState.IDLE
        self.agent_id = str(uuid.uuid4())

        # Metrics
        self.metrics = {
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_runtime_seconds': 0,
            'last_task_time': None,
            'errors': []
        }

        # Personality traits (override in subclasses)
        self.personality = {}

        # Dependencies
        self.message_bus = None
        self.started_at = datetime.now()

        logger.info(f"Agent {self.agent_name} ({self.agent_id}) created")

    # ==================== Lifecycle Methods ====================

    async def initialize(self):
        """
        Initialize agent resources

        Override this method to:
        - Connect to APIs
        - Load models
        - Set up connections
        - Validate configuration
        """
        logger.info(f"[{self.agent_name}] Initializing...")
        self.state = AgentState.INITIALIZING

        try:
            # Perform initialization
            await self._initialize()

            # Connect to message bus
            await self._connect_message_bus()

            self.state = AgentState.READY
            logger.info(f"[{self.agent_name}] Ready")

        except Exception as e:
            self.state = AgentState.ERROR
            logger.error(f"[{self.agent_name}] Initialization failed: {e}")
            raise

    @abstractmethod
    async def _initialize(self):
        """Subclass-specific initialization"""
        pass

    async def start(self):
        """Start the agent"""
        if self.state != AgentState.READY:
            await self.initialize()

        logger.info(f"[{self.agent_name}] Starting...")
        await self._start_main_loop()

    async def pause(self):
        """Pause agent operations"""
        logger.info(f"[{self.agent_name}] Pausing...")
        self.state = AgentState.PAUSED

    async def resume(self):
        """Resume agent operations"""
        logger.info(f"[{self.agent_name}] Resuming...")
        self.state = AgentState.WORKING

    async def shutdown(self):
        """Gracefully shut down agent"""
        logger.info(f"[{self.agent_name}] Shutting down...")
        self.state = AgentState.SHUTDOWN

        try:
            await self._shutdown()
            logger.info(f"[{self.agent_name}] Shutdown complete")
        except Exception as e:
            logger.error(f"[{self.agent_name}] Shutdown error: {e}")

    @abstractmethod
    async def _shutdown(self):
        """Subclass-specific shutdown"""
        pass

    # ==================== Task Execution ====================

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task

        Args:
            task: Task dictionary with parameters

        Returns:
            Result dictionary
        """
        task_id = task.get('task_id', 'unknown')
        logger.info(f"[{self.agent_name}] Executing task {task_id}")

        self.state = AgentState.WORKING
        start_time = datetime.now()

        try:
            # Perform task
            result = await self._execute_task(task)

            # Update metrics
            duration = (datetime.now() - start_time).total_seconds()
            self.metrics['tasks_completed'] += 1
            self.metrics['total_runtime_seconds'] += duration
            self.metrics['last_task_time'] = datetime.now().isoformat()

            self.state = AgentState.READY

            logger.info(
                f"[{self.agent_name}] Task {task_id} completed "
                f"in {duration:.2f}s"
            )

            return {
                'status': 'completed',
                'task_id': task_id,
                'duration_seconds': duration,
                'result': result
            }

        except Exception as e:
            # Handle error
            self.metrics['tasks_failed'] += 1
            self.metrics['errors'].append({
                'task_id': task_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

            self.state = AgentState.ERROR
            logger.error(f"[{self.agent_name}] Task {task_id} failed: {e}")

            # Notify error recovery agent
            await self._report_error(task_id, e)

            return {
                'status': 'failed',
                'task_id': task_id,
                'error': str(e)
            }

    @abstractmethod
    async def _execute_task(self, task: Dict[str, Any]) -> Any:
        """
        Subclass-specific task execution

        Args:
            task: Task parameters

        Returns:
            Task result
        """
        pass

    # ==================== Message Bus Communication ====================

    async def _connect_message_bus(self):
        """Connect to message bus"""
        # TODO: Implement actual message bus connection
        logger.info(f"[{self.agent_name}] Connected to message bus")
        pass

    async def send_message(
        self,
        to: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: int = 3
    ):
        """
        Send message to another agent

        Args:
            to: Recipient agent name
            message_type: Type of message
            payload: Message payload
            priority: Message priority (1-5)
        """
        message = {
            'message_id': str(uuid.uuid4()),
            'from': self.agent_name,
            'to': to,
            'message_type': message_type,
            'priority': priority,
            'timestamp': datetime.now().isoformat(),
            'payload': payload
        }

        logger.debug(f"[{self.agent_name}] → {to}: {message_type}")

        # TODO: Implement actual message sending
        pass

    async def broadcast_message(
        self,
        message_type: str,
        payload: Dict[str, Any],
        priority: int = 2
    ):
        """Broadcast message to all agents"""
        await self.send_message(
            to='broadcast',
            message_type=message_type,
            payload=payload,
            priority=priority
        )

    # ==================== Health Monitoring ====================

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check

        Returns:
            Health status dictionary
        """
        uptime = (datetime.now() - self.started_at).total_seconds()

        health = {
            'agent_name': self.agent_name,
            'agent_id': self.agent_id,
            'state': self.state.value,
            'uptime_seconds': uptime,
            'tasks_completed': self.metrics['tasks_completed'],
            'tasks_failed': self.metrics['tasks_failed'],
            'error_rate': self._calculate_error_rate(),
            'last_task_time': self.metrics['last_task_time'],
            'status': self._determine_health_status()
        }

        # Add subclass-specific health info
        custom_health = await self._custom_health_check()
        if custom_health:
            health.update(custom_health)

        return health

    async def _custom_health_check(self) -> Optional[Dict[str, Any]]:
        """Subclass-specific health checks"""
        return None

    def _calculate_error_rate(self) -> float:
        """Calculate error rate"""
        total = self.metrics['tasks_completed'] + self.metrics['tasks_failed']
        if total == 0:
            return 0.0
        return self.metrics['tasks_failed'] / total

    def _determine_health_status(self) -> str:
        """Determine overall health status"""
        if self.state == AgentState.ERROR:
            return 'unhealthy'
        elif self.state == AgentState.SHUTDOWN:
            return 'offline'
        elif self._calculate_error_rate() > 0.1:
            return 'degraded'
        else:
            return 'healthy'

    # ==================== Error Handling ====================

    async def _report_error(self, task_id: str, error: Exception):
        """Report error to error recovery agent"""
        await self.send_message(
            to='error_recovery_agent',
            message_type='error_report',
            payload={
                'task_id': task_id,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'agent_state': self.state.value,
                'timestamp': datetime.now().isoformat()
            },
            priority=4
        )

    # ==================== Main Loop ====================

    async def _start_main_loop(self):
        """Main agent loop (for autonomous agents)"""
        logger.info(f"[{self.agent_name}] Main loop started")

        try:
            while self.state != AgentState.SHUTDOWN:
                if self.state == AgentState.PAUSED:
                    await asyncio.sleep(1)
                    continue

                # Check for messages/tasks
                # TODO: Implement task queue processing

                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"[{self.agent_name}] Main loop error: {e}")
            self.state = AgentState.ERROR

    # ==================== Utility Methods ====================

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def log_info(self, message: str):
        """Log info message"""
        logger.info(f"[{self.agent_name}] {message}")

    def log_warning(self, message: str):
        """Log warning message"""
        logger.warning(f"[{self.agent_name}] {message}")

    def log_error(self, message: str):
        """Log error message"""
        logger.error(f"[{self.agent_name}] {message}")

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.agent_name} ({self.state.value})>"
