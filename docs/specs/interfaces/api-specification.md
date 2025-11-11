# API Specification

## Overview

This document defines the API interfaces for the modernized BettaFish system, including REST endpoints, WebSocket connections, and internal service communication protocols.

## REST API Endpoints

### Base Configuration
```
Base URL: http://localhost:8000/api/v1
API Version: v1
Content-Type: application/json
Authentication: Bearer Token (optional for public endpoints)
```

### 1. Agent Management

#### List All Agents
```http
GET /agents
```

**Response:**
```json
{
  "agents": [
    {
      "id": "insight-engine",
      "name": "Insight Engine",
      "type": "analysis",
      "status": "running",
      "capabilities": ["sentiment-analysis", "keyword-extraction"],
      "endpoints": {
        "health": "/agents/insight-engine/health",
        "query": "/agents/insight-engine/query"
      }
    }
  ]
}
```

#### Get Agent Details
```http
GET /agents/{agent_id}
```

#### Update Agent Configuration
```http
PUT /agents/{agent_id}/config
Content-Type: application/json

{
  "model_name": "gpt-4o-mini",
  "max_tokens": 4000,
  "temperature": 0.1
}
```

### 2. Query and Analysis

#### Submit Analysis Query
```http
POST /query
Content-Type: application/json

{
  "query": "Analyze sentiment about electric vehicles",
  "agents": ["insight-engine", "media-engine"],
  "parameters": {
    "time_range": "7d",
    "sources": ["news", "social"],
    "language": "en"
  },
  "options": {
    "stream": true,
    "include_raw_data": false
  }
}
```

**Response:**
```json
{
  "query_id": "uuid-string",
  "status": "processing",
  "estimated_duration": 45,
  "websocket_url": "/ws/query/uuid-string"
}
```

#### Get Query Status
```http
GET /query/{query_id}
```

**Response:**
```json
{
  "query_id": "uuid-string",
  "status": "completed",
  "progress": 100,
  "results": {
    "summary": "Overall sentiment is positive...",
    "detailed_analysis": {...},
    "metadata": {
      "processing_time": 42.5,
      "agents_used": ["insight-engine", "media-engine"],
      "data_points": 1250
    }
  }
}
```

#### Cancel Query
```http
DELETE /query/{query_id}
```

### 3. Data Management

#### Search Historical Data
```http
GET /data/search
Query Parameters:
- q: search query
- date_from: ISO date string
- date_to: ISO date string
- source: data source filter
- limit: result count (default: 50)
- offset: pagination offset

Example: GET /data/search?q=electric%20vehicles&date_from=2024-01-01&limit=20
```

#### Export Data
```http
POST /data/export
Content-Type: application/json

{
  "query_id": "uuid-string",
  "format": "json|csv|xlsx",
  "include_raw": false,
  "filters": {
    "sentiment": ["positive", "negative"],
    "sources": ["news"]
  }
}
```

**Response:**
```json
{
  "export_id": "uuid-string",
  "download_url": "/data/download/uuid-string",
  "expires_at": "2024-01-02T00:00:00Z"
}
```

### 4. Configuration Management

#### Get System Configuration
```http
GET /config
```

#### Update System Configuration
```http
PUT /config
Content-Type: application/json

{
  "llm_providers": {
    "openai": {
      "api_key": "encrypted-key",
      "models": ["gpt-4", "gpt-4o-mini"]
    }
  },
  "database": {
    "connection_pool_size": 10
  }
}
```

### 5. Monitoring and Health

#### System Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "uptime": 86400,
  "components": {
    "orchestrator": "healthy",
    "agents": {
      "insight-engine": "healthy",
      "media-engine": "healthy",
      "query-engine": "healthy",
      "report-engine": "healthy"
    },
    "database": "healthy",
    "external_apis": {
      "tavily": "healthy",
      "openai": "healthy"
    }
  }
}
```

#### Metrics Endpoint
```http
GET /metrics
```

**Response:**
```json
{
  "performance": {
    "avg_query_time": 45.2,
    "queries_per_hour": 125,
    "success_rate": 98.5
  },
  "resources": {
    "cpu_usage": 45.2,
    "memory_usage": 68.1,
    "disk_usage": 23.4
  },
  "agents": {
    "active_queries": 3,
    "total_processed": 1250
  }
}
```

## WebSocket API

### Connection Endpoint
```
ws://localhost:8000/ws
```

### Authentication
```javascript
// Send authentication message after connection
{
  "type": "auth",
  "token": "bearer-token"
}
```

### Query Progress Streaming
```javascript
// Connect to specific query stream
ws://localhost:8000/ws/query/{query_id}

// Messages received:
{
  "type": "progress",
  "query_id": "uuid-string",
  "agent": "insight-engine",
  "progress": 45,
  "message": "Processing sentiment analysis...",
  "data": {
    "partial_results": {...}
  }
}

{
  "type": "completed",
  "query_id": "uuid-string",
  "results": {...}
}

{
  "type": "error",
  "query_id": "uuid-string",
  "error": "Agent processing failed"
}
```

### Real-time Monitoring
```javascript
// Connect to system monitoring stream
ws://localhost:8000/ws/monitor

// Messages received:
{
  "type": "system_metrics",
  "timestamp": "2024-01-01T12:00:00Z",
  "cpu": 45.2,
  "memory": 68.1,
  "active_queries": 3
}

{
  "type": "agent_status",
  "agent_id": "insight-engine",
  "status": "processing",
  "current_task": "sentiment-analysis"
}
```

## Internal Service APIs

### Agent-to-Agent Communication

#### Message Format
```json
{
  "id": "message-uuid",
  "from": "insight-engine",
  "to": "media-engine",
  "type": "data_request",
  "timestamp": "2024-01-01T12:00:00Z",
  "payload": {
    "query": "Get media data for sentiment analysis",
    "parameters": {...}
  }
}
```

#### Service Discovery
```json
GET /internal/services
Response:
{
  "services": [
    {
      "name": "insight-engine",
      "host": "insight-engine",
      "port": 8001,
      "health": "/health",
      "version": "2.0.0"
    }
  ]
}
```

### Database Access Layer

#### Query Interface
```json
POST /internal/db/query
{
  "query_type": "select|insert|update",
  "table": "sentiment_analysis",
  "parameters": {...},
  "limit": 100
}
```

#### Cache Interface
```json
GET /internal/cache/{key}
PUT /internal/cache/{key}
DELETE /internal/cache/{key}
```

## Error Handling

### HTTP Status Codes
- `200 OK` - Successful request
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict
- `422 Unprocessable Entity` - Validation error
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid query parameters",
    "details": {
      "field": "time_range",
      "issue": "Invalid date format"
    },
    "request_id": "req-uuid",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

### Common Error Codes
- `VALIDATION_ERROR` - Request validation failed
- `AGENT_UNAVAILABLE` - Specified agent is not running
- `QUERY_TIMEOUT` - Query processing exceeded time limit
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INSUFFICIENT_PERMISSIONS` - User lacks required permissions
- `EXTERNAL_API_ERROR` - Third-party API failure
- `DATABASE_ERROR` - Database operation failed

## Rate Limiting

### Endpoint Limits
- `/query`: 10 requests per minute per user
- `/data/search`: 60 requests per minute per user
- `/agents/*`: 30 requests per minute per user
- `/config`: 5 requests per minute per user

### Rate Limit Headers
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1640995200
```

## API Versioning

### Version Strategy
- URL path versioning: `/api/v1/`, `/api/v2/`
- Backward compatibility maintained for at least 2 versions
- Deprecation warnings sent in response headers

### Version Response Headers
```http
API-Version: v1
API-Deprecated: false
API-Sunset: 2025-01-01
```

## Security Considerations

### Authentication
- JWT-based authentication for sensitive endpoints
- API key authentication for service-to-service communication
- Optional authentication for public endpoints

### Authorization
- Role-based access control (RBAC)
- Resource-level permissions
- Agent-specific access controls

### Input Validation
- All inputs validated against JSON schemas
- SQL injection prevention
- XSS protection in all text inputs

### CORS Configuration
```javascript
{
  "origin": ["http://localhost:3000", "https://bettafish.example.com"],
  "methods": ["GET", "POST", "PUT", "DELETE"],
  "allowed_headers": ["Content-Type", "Authorization"],
  "credentials": true
}
```

## API Documentation

### OpenAPI Specification
- Full OpenAPI 3.0 specification available at `/openapi.json`
- Interactive API documentation at `/docs` (Swagger UI)
- Alternative documentation at `/redoc` (ReDoc)

### Schema Examples
All endpoints include comprehensive JSON schema examples for requests and responses, with detailed field descriptions and validation rules.

## Testing and Mocking

### Mock Server
- Mock API server available for development
- Consistent response formats and error handling
- Configurable latency and error scenarios

### Contract Testing
- API contract tests using OpenAPI specification
- Consumer-driven contract testing for internal services
- Automated testing in CI/CD pipeline

This API specification provides a comprehensive interface definition for the modernized BettaFish system, ensuring consistent, secure, and scalable communication between all components.