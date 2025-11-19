# BettaFish Inter-Agent Communication Protocol

## Overview

This document defines the communication protocols, message formats, and coordination patterns for agent-to-agent interaction in the BettaFish Western Media Monitoring system.

**Version:** 1.0
**Last Updated:** 2025-01-19
**Based on:** Anthropic Multi-Agent Best Practices

---

## Communication Architecture

### Message Bus Pattern

All agents communicate through a centralized message bus (Redis-based pub/sub):

```
┌──────────┐       ┌──────────────┐       ┌──────────┐
│ Agent A  │──────►│ Message Bus  │──────►│ Agent B  │
└──────────┘       │  (Redis)     │       └──────────┘
                   └──────────────┘
                          │
                   ┌──────▼──────┐
                   │Message Store│
                   │(Persistence)│
                   └─────────────┘
```

### Benefits
- **Decoupling**: Agents don't need to know about each other
- **Scalability**: Easy to add new agents
- **Reliability**: Messages can be persisted
- **Observability**: All communication is logged

---

## Message Format Standard

### Base Message Structure

All messages follow this JSON schema:

```json
{
  "message_id": "uuid-v4",
  "from": "agent_name",
  "to": "agent_name | broadcast",
  "message_type": "enum",
  "priority": 1-5,
  "timestamp": "ISO-8601",
  "correlation_id": "uuid-v4",
  "headers": {
    "retry_count": 0,
    "max_retries": 3,
    "timeout_ms": 30000
  },
  "payload": {}
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message_id` | UUID | Yes | Unique message identifier |
| `from` | String | Yes | Sending agent name |
| `to` | String | Yes | Receiving agent name (or "broadcast") |
| `message_type` | Enum | Yes | Type of message (see types below) |
| `priority` | Integer | Yes | 1=lowest, 5=highest |
| `timestamp` | ISO-8601 | Yes | Message creation time |
| `correlation_id` | UUID | No | Links related messages (e.g., request/response) |
| `headers` | Object | No | Metadata for message handling |
| `payload` | Object | Yes | Message-specific content |

---

## Message Types

### 1. Task Assignment

**Direction:** Project Manager → Platform Agent

```json
{
  "message_type": "task_assignment",
  "from": "project_manager_agent",
  "to": "reddit_agent",
  "priority": 3,
  "payload": {
    "task_id": "T-20250119-0001",
    "task_type": "monitor_subreddits",
    "deadline": "2025-01-19T18:00:00Z",
    "parameters": {
      "subreddits": ["politics", "conservative", "neutralpolitics"],
      "posts_per_sub": 25,
      "fetch_comments": true,
      "max_comments_per_post": 50
    },
    "constraints": {
      "max_duration_seconds": 600,
      "rate_limit_group": "reddit_standard"
    }
  }
}
```

---

### 2. Task Acknowledgment

**Direction:** Platform Agent → Project Manager

```json
{
  "message_type": "task_ack",
  "from": "reddit_agent",
  "to": "project_manager_agent",
  "priority": 3,
  "correlation_id": "same-as-task-assignment",
  "payload": {
    "task_id": "T-20250119-0001",
    "status": "accepted",
    "estimated_duration_seconds": 420,
    "start_time": "2025-01-19T16:30:00Z"
  }
}
```

Possible `status` values:
- `accepted`: Task accepted and will begin
- `rejected`: Task rejected (with reason in payload)
- `queued`: Task queued for later execution

---

### 3. Task Status Update

**Direction:** Any Agent → Project Manager

```json
{
  "message_type": "task_status",
  "from": "reddit_agent",
  "to": "project_manager_agent",
  "priority": 2,
  "correlation_id": "same-as-task-assignment",
  "payload": {
    "task_id": "T-20250119-0001",
    "status": "in_progress",
    "progress_percent": 45,
    "items_processed": 102,
    "items_total": 225,
    "estimated_completion": "2025-01-19T16:45:00Z",
    "current_activity": "Collecting comments from r/politics"
  }
}
```

Possible `status` values:
- `queued`: Waiting to start
- `in_progress`: Currently executing
- `paused`: Temporarily paused
- `completed`: Successfully finished
- `failed`: Failed with error
- `cancelled`: Cancelled by user/system

---

### 4. Task Completion

**Direction:** Any Agent → Project Manager

```json
{
  "message_type": "task_completed",
  "from": "reddit_agent",
  "to": "project_manager_agent",
  "priority": 3,
  "correlation_id": "same-as-task-assignment",
  "payload": {
    "task_id": "T-20250119-0001",
    "status": "completed",
    "result": {
      "subreddits_monitored": 3,
      "posts_collected": 75,
      "comments_collected": 1250,
      "duration_seconds": 380,
      "data_location": "storage://reddit/2025-01-19/batch-0001"
    },
    "metrics": {
      "api_calls": 150,
      "rate_limit_usage": "60%",
      "errors": 2,
      "warnings": 5
    },
    "next_recommended_run": "2025-01-19T22:00:00Z"
  }
}
```

---

### 5. Data Transfer

**Direction:** Platform Agent → Data Pipeline Agent

```json
{
  "message_type": "data_delivery",
  "from": "reddit_agent",
  "to": "data_pipeline_agent",
  "priority": 3,
  "payload": {
    "task_id": "T-20250119-0001",
    "data_type": "reddit_posts",
    "format": "json",
    "count": 75,
    "size_bytes": 524288,
    "data": [
      {
        "post_id": "abc123",
        "subreddit": "politics",
        "title": "...",
        "content": "...",
        "score": 1250,
        "num_comments": 342,
        "created_utc": 1705689600
      }
    ],
    "metadata": {
      "collection_time": "2025-01-19T16:45:00Z",
      "source_platform": "reddit",
      "quality_score": 0.95
    }
  }
}
```

For large datasets, use reference instead of inline data:

```json
{
  "message_type": "data_delivery",
  "from": "reddit_agent",
  "to": "data_pipeline_agent",
  "priority": 3,
  "payload": {
    "task_id": "T-20250119-0001",
    "data_type": "reddit_posts",
    "format": "json",
    "count": 75,
    "size_bytes": 524288,
    "data_reference": {
      "type": "s3",
      "bucket": "bettafish-data",
      "key": "reddit/2025-01-19/batch-0001.json",
      "ttl_seconds": 3600
    }
  }
}
```

---

### 6. Rate Limit Check

**Direction:** Platform Agent → Rate Limiter Agent

```json
{
  "message_type": "rate_limit_check",
  "from": "twitter_agent",
  "to": "rate_limiter_agent",
  "priority": 4,
  "payload": {
    "platform": "twitter",
    "requested_operations": 10,
    "operation_type": "api_call"
  }
}
```

**Response:**

```json
{
  "message_type": "rate_limit_response",
  "from": "rate_limiter_agent",
  "to": "twitter_agent",
  "priority": 4,
  "correlation_id": "same-as-check",
  "payload": {
    "approved": true,
    "approved_operations": 10,
    "current_usage": {
      "requests_this_hour": 15,
      "limit_per_hour": 20,
      "remaining": 5,
      "reset_time": "2025-01-19T17:00:00Z"
    },
    "recommended_delay_seconds": 15.0
  }
}
```

If denied:

```json
{
  "payload": {
    "approved": false,
    "reason": "Rate limit exceeded",
    "retry_after_seconds": 1200,
    "current_usage": {
      "requests_this_hour": 20,
      "limit_per_hour": 20,
      "remaining": 0,
      "reset_time": "2025-01-19T17:00:00Z"
    }
  }
}
```

---

### 7. Health Check

**Direction:** Any Agent → Health Monitor Agent (broadcast)

```json
{
  "message_type": "health_status",
  "from": "reddit_agent",
  "to": "health_monitor_agent",
  "priority": 2,
  "payload": {
    "status": "healthy",
    "uptime_seconds": 86400,
    "tasks_completed": 145,
    "tasks_failed": 3,
    "error_rate": 0.02,
    "avg_task_duration_seconds": 380,
    "resource_usage": {
      "cpu_percent": 35.5,
      "memory_mb": 512,
      "disk_mb": 1024
    },
    "last_successful_task": "2025-01-19T16:45:00Z",
    "dependencies_healthy": true
  }
}
```

Possible `status` values:
- `healthy`: All systems operational
- `degraded`: Operating but with issues
- `unhealthy`: Critical issues
- `offline`: Not responding

---

### 8. Error Report

**Direction:** Any Agent → Error Recovery Agent, Project Manager

```json
{
  "message_type": "error_report",
  "from": "twitter_agent",
  "to": "error_recovery_agent",
  "priority": 5,
  "payload": {
    "task_id": "T-20250119-0042",
    "error_type": "RateLimitError",
    "severity": "high",
    "error_message": "Twitter API rate limit exceeded",
    "error_code": "429",
    "context": {
      "publisher": "@CNN",
      "operation": "fetch_tweets",
      "retry_count": 3,
      "last_successful_request": "2025-01-19T16:30:00Z"
    },
    "stack_trace": "...",
    "recovery_suggestion": "Wait 20 minutes and retry"
  }
}
```

Severity levels:
- `low`: Minor issue, can continue
- `medium`: Issue affecting quality
- `high`: Issue affecting operations
- `critical`: System-wide impact

---

### 9. Alert

**Direction:** Any Agent → Project Manager (urgent issues)

```json
{
  "message_type": "alert",
  "from": "rate_limiter_agent",
  "to": "project_manager_agent",
  "priority": 5,
  "payload": {
    "alert_type": "ip_ban_risk",
    "severity": "critical",
    "title": "Twitter rate limit at 95%",
    "description": "Twitter agent approaching rate limit. Recommend emergency pause.",
    "recommended_action": "pause_twitter_agent",
    "time_to_act_seconds": 300,
    "auto_action_enabled": true
  }
}
```

---

### 10. Command

**Direction:** Project Manager → Any Agent

```json
{
  "message_type": "command",
  "from": "project_manager_agent",
  "to": "twitter_agent",
  "priority": 5,
  "payload": {
    "command": "emergency_pause",
    "reason": "Rate limit exceeded",
    "duration_seconds": 1200,
    "resume_condition": "manual"
  }
}
```

Commands:
- `start`: Start agent
- `stop`: Stop agent gracefully
- `pause`: Pause agent temporarily
- `resume`: Resume from pause
- `emergency_stop`: Stop immediately
- `restart`: Restart agent
- `reload_config`: Reload configuration

---

### 11. Broadcast

**Direction:** Any Agent → All Agents

```json
{
  "message_type": "broadcast",
  "from": "project_manager_agent",
  "to": "broadcast",
  "priority": 4,
  "payload": {
    "announcement_type": "system_maintenance",
    "message": "System maintenance in 10 minutes. Please complete current tasks.",
    "scheduled_time": "2025-01-19T18:00:00Z",
    "expected_duration_minutes": 15,
    "affected_agents": ["all"]
  }
}
```

---

## Communication Patterns

### 1. Request-Response Pattern

Used for synchronous operations:

```python
# Sender (Reddit Agent)
request_id = str(uuid.uuid4())
bus.publish('rate_limit_check', {
    'message_id': request_id,
    'from': 'reddit_agent',
    'to': 'rate_limiter_agent',
    'payload': {'platform': 'reddit', 'operations': 10}
})

# Wait for response (with timeout)
response = await bus.wait_for_response(request_id, timeout=5.0)

if response['payload']['approved']:
    # Proceed with operation
    pass
else:
    # Wait as recommended
    await asyncio.sleep(response['payload']['retry_after_seconds'])
```

---

### 2. Pub-Sub Pattern

Used for event broadcasting:

```python
# Publisher (Reddit Agent)
bus.publish('data.collected', {
    'from': 'reddit_agent',
    'payload': {
        'platform': 'reddit',
        'items': 150,
        'timestamp': datetime.now().isoformat()
    }
})

# Subscribers (multiple agents can listen)
# Data Pipeline Agent
bus.subscribe('data.collected', handle_new_data)

# Monitoring Agent
bus.subscribe('data.collected', record_metric)

# Storage Agent
bus.subscribe('data.collected', prepare_storage)
```

---

### 3. Task Queue Pattern

Used for distributed work:

```python
# Project Manager (adds tasks to queue)
task_queue.enqueue({
    'task_id': 'T-001',
    'type': 'monitor_reddit',
    'priority': 3,
    'params': {...}
})

# Reddit Agent (pulls from queue)
while True:
    task = task_queue.dequeue(agent_name='reddit_agent')
    if task:
        await execute_task(task)
```

---

### 4. Circuit Breaker Pattern

Used for error recovery:

```python
class CircuitBreaker:
    states = ['CLOSED', 'OPEN', 'HALF_OPEN']

    def __init__(self, failure_threshold=5, timeout=60):
        self.state = 'CLOSED'
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout

    async def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpen("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                self.last_failure = time.time()
                bus.publish('alert', {
                    'from': self.agent_name,
                    'alert_type': 'circuit_breaker_open',
                    'service': func.__name__
                })
            raise
```

---

## Priority System

Messages are processed based on priority:

| Priority | Level | Description | Examples |
|----------|-------|-------------|----------|
| 5 | Critical | Immediate action required | Alerts, emergency commands, IP ban warnings |
| 4 | High | Important but not emergency | Rate limit checks, error reports |
| 3 | Normal | Standard operations | Task assignments, data delivery |
| 2 | Low | Background operations | Health checks, metrics |
| 1 | Minimal | Nice-to-have | Logs, debug info |

Priority queue processing:
```python
# Higher priority messages processed first
while True:
    message = message_queue.pop_highest_priority()
    await process_message(message)
```

---

## Message Persistence

### When to Persist

Messages are persisted based on type:

| Message Type | Persist | TTL | Reason |
|--------------|---------|-----|--------|
| task_assignment | Yes | 7 days | Audit trail |
| task_completed | Yes | 30 days | Metrics and reporting |
| data_delivery | No | N/A | Too large, stored elsewhere |
| health_status | Yes | 24 hours | Trend analysis |
| error_report | Yes | 90 days | Debugging |
| rate_limit_check | No | N/A | Too frequent |

### Storage

```python
# Persist message
await message_store.save(message_id, {
    'message': message,
    'timestamp': datetime.now(),
    'ttl_seconds': 86400
})

# Retrieve message
message = await message_store.get(message_id)
```

---

## Message Validation

All messages must pass validation:

```python
from jsonschema import validate

def validate_message(message):
    schema = {
        "type": "object",
        "required": ["message_id", "from", "to", "message_type", "payload"],
        "properties": {
            "message_id": {"type": "string", "format": "uuid"},
            "from": {"type": "string", "minLength": 1},
            "to": {"type": "string", "minLength": 1},
            "message_type": {"type": "string", "enum": [...]},
            "priority": {"type": "integer", "minimum": 1, "maximum": 5},
            "payload": {"type": "object"}
        }
    }

    try:
        validate(instance=message, schema=schema)
        return True
    except ValidationError as e:
        log_error(f"Invalid message: {e}")
        return False
```

---

## Error Handling

### Retry Strategy

```python
async def send_with_retry(message, max_retries=3):
    for attempt in range(max_retries):
        try:
            await bus.publish(message)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                delay = 2 ** attempt  # Exponential backoff
                await asyncio.sleep(delay)
            else:
                # Final attempt failed
                await bus.publish({
                    'message_type': 'error_report',
                    'from': 'message_bus',
                    'to': 'error_recovery_agent',
                    'payload': {
                        'error': f'Failed to deliver message after {max_retries} attempts',
                        'original_message': message
                    }
                })
                return False
```

---

## Message Bus Implementation

### Redis-based Implementation

```python
import redis.asyncio as redis
import json

class MessageBus:
    def __init__(self):
        self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
        self.subscribers = {}

    async def publish(self, channel, message):
        """Publish message to channel"""
        if not validate_message(message):
            raise ValueError("Invalid message format")

        message_json = json.dumps(message)
        await self.redis.publish(channel, message_json)

        # Persist if needed
        if should_persist(message):
            await self.persist_message(message)

    async def subscribe(self, channel, callback):
        """Subscribe to channel"""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                await callback(data)

    async def request_response(self, channel, message, timeout=30.0):
        """Send request and wait for response"""
        correlation_id = str(uuid.uuid4())
        message['correlation_id'] = correlation_id

        # Subscribe to response channel
        response_channel = f"response.{correlation_id}"
        response_future = asyncio.Future()

        async def handle_response(msg):
            response_future.set_result(msg)

        await self.subscribe(response_channel, handle_response)

        # Publish request
        await self.publish(channel, message)

        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            raise TimeoutError(f"No response received within {timeout}s")
```

---

## Monitoring Communication

### Message Metrics

Track these metrics:

```python
class MessageMetrics:
    def __init__(self):
        self.metrics = {
            'messages_sent': Counter(),
            'messages_received': Counter(),
            'message_latency': Histogram(),
            'message_errors': Counter(),
            'messages_by_type': Counter(),
            'messages_by_priority': Counter()
        }

    def record_send(self, message):
        self.metrics['messages_sent'].inc()
        self.metrics['messages_by_type'].labels(
            type=message['message_type']
        ).inc()

    def record_latency(self, message, duration_ms):
        self.metrics['message_latency'].observe(duration_ms)
```

### Dashboards

Create dashboards to visualize:
- Messages per second by type
- Average message latency
- Error rate by agent
- Queue depths
- Response times

---

## Security

### Message Authentication

```python
import hmac
import hashlib

def sign_message(message, secret_key):
    """Sign message with HMAC"""
    message_json = json.dumps(message, sort_keys=True)
    signature = hmac.new(
        secret_key.encode(),
        message_json.encode(),
        hashlib.sha256
    ).hexdigest()
    message['signature'] = signature
    return message

def verify_message(message, secret_key):
    """Verify message signature"""
    signature = message.pop('signature', None)
    message_json = json.dumps(message, sort_keys=True)
    expected_signature = hmac.new(
        secret_key.encode(),
        message_json.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature == expected_signature
```

### Authorization

```python
# Agent permissions
PERMISSIONS = {
    'reddit_agent': ['publish:data.reddit', 'subscribe:tasks.reddit'],
    'project_manager_agent': ['publish:*', 'subscribe:*'],
    'rate_limiter_agent': ['publish:rate_limit.*', 'subscribe:rate_limit.check']
}

def check_permission(agent, action, channel):
    """Check if agent has permission"""
    permissions = PERMISSIONS.get(agent, [])
    for perm in permissions:
        if fnmatch.fnmatch(f"{action}:{channel}", perm):
            return True
    return False
```

---

## Best Practices

### 1. Keep Messages Small
- Use data references for large payloads
- Compress data if needed
- Paginate large result sets

### 2. Use Correlation IDs
- Link related messages
- Trace workflows end-to-end
- Debug issues easily

### 3. Set Timeouts
- Always set timeouts for request-response
- Use reasonable defaults (30s)
- Handle timeout gracefully

### 4. Handle Errors
- Always include error handling
- Use exponential backoff for retries
- Log all errors

### 5. Monitor Everything
- Track all message types
- Measure latency
- Alert on anomalies

### 6. Version Messages
- Include version in message
- Support backward compatibility
- Plan for schema evolution

---

## Example: Complete Workflow

### Reddit Monitoring Workflow

```python
# 1. Project Manager assigns task
await bus.publish('tasks.reddit', {
    'message_type': 'task_assignment',
    'from': 'project_manager_agent',
    'to': 'reddit_agent',
    'task_id': 'T-001',
    'payload': {'subreddits': ['politics'], 'posts_per_sub': 25}
})

# 2. Reddit Agent checks rate limit
response = await bus.request_response('rate_limit.check', {
    'from': 'reddit_agent',
    'to': 'rate_limiter_agent',
    'platform': 'reddit',
    'operations': 25
})

# 3. If approved, collect data
if response['approved']:
    data = await collect_reddit_data()

    # 4. Send data to pipeline
    await bus.publish('data.collected', {
        'from': 'reddit_agent',
        'to': 'data_pipeline_agent',
        'data': data
    })

    # 5. Report completion
    await bus.publish('tasks.completed', {
        'from': 'reddit_agent',
        'to': 'project_manager_agent',
        'task_id': 'T-001',
        'status': 'completed',
        'items': len(data)
    })
```

---

**Document Version:** 1.0
**Last Updated:** 2025-01-19
**Next Review:** As system evolves
**Owner:** Technical Lead
