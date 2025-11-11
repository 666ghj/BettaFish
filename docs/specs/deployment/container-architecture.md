# Container Architecture

## Overview

This document defines the container architecture for the modernized BettaFish system, providing a scalable, maintainable, and deployment-ready containerization strategy using Docker and Docker Compose.

## Container Strategy

### Design Principles
1. **Single Responsibility**: Each container has a single, well-defined purpose
2. **Stateless Design**: Application containers are stateless where possible
3. **Configuration via Environment**: All configuration through environment variables
4. **Health Checks**: Comprehensive health monitoring for all containers
5. **Resource Limits**: Defined resource constraints for stability
6. **Security**: Minimal base images and non-root execution

### Container Hierarchy
```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer                            │
│                   (Nginx/HAProxy)                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────┐
│                  API Gateway                                │
│                 (FastAPI/uvicorn)                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
┌───▼────┐    ┌──────▼──────┐    ┌─────▼─────┐
│Insight │    │   Media     │    │  Query    │
│Engine  │    │   Engine    │    │  Engine   │
└────────┘    └─────────────┘    └───────────┘
    │                 │                 │
    └─────────────────┼─────────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
┌───▼────┐    ┌──────▼──────┐    ┌─────▼─────┐
│Report  │    │   Forum     │    │  State    │
│Engine  │    │   Engine    │    │Management │
└────────┘    └─────────────┘    └───────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
┌───▼────┐    ┌──────▼──────┐    ┌─────▼─────┐
│Database│    │    Redis    │    │Monitoring │
│(Postgres)│   │   (Cache)   │  │(Prometheus)│
└────────┘    └─────────────┘    └───────────┘
```

## Core Application Containers

### 1. API Gateway Container

```dockerfile
# containers/api-gateway/Dockerfile
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create necessary directories
RUN mkdir -p /app/logs /app/uploads && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 2. Insight Engine Container

```dockerfile
# containers/insight-engine/Dockerfile
FROM python:3.11-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies for ML models
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r insightuser && useradd -r -g insightuser insightuser

WORKDIR /app

# Copy requirements
COPY requirements.txt requirements-insight.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r requirements-insight.txt

# Copy application code
COPY src/agents/insight_engine/ ./src/agents/insight_engine/
COPY src/tools/ ./src/tools/
COPY src/state/ ./src/state/
COPY src/utils/ ./src/utils/

# Download ML models if needed
RUN python -c "from src.agents.insight_engine.models import download_models; download_models()" || true

# Create directories
RUN mkdir -p /app/logs /app/models /app/data && \
    chown -R insightuser:insightuser /app

USER insightuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/health')" || exit 1

EXPOSE 8001

CMD ["uvicorn", "src.agents.insight_engine.app:app", "--host", "0.0.0.0", "--port", "8001"]
```

### 3. Media Engine Container

```dockerfile
# containers/media-engine/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r mediauser && useradd -r -g mediauser mediauser

WORKDIR /app

COPY requirements.txt requirements-media.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r requirements-media.txt

COPY src/agents/media_engine/ ./src/agents/media_engine/
COPY src/tools/ ./src/tools/
COPY src/state/ ./src/state/

RUN mkdir -p /app/logs /app/media && \
    chown -R mediauser:mediauser /app

USER mediauser

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

EXPOSE 8002

CMD ["uvicorn", "src.agents.media_engine.app:app", "--host", "0.0.0.0", "--port", "8002"]
```

### 4. Query Engine Container

```dockerfile
# containers/query-engine/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r queryuser && useradd -r -g queryuser queryuser

WORKDIR /app

COPY requirements.txt requirements-query.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r requirements-query.txt

COPY src/agents/query_engine/ ./src/agents/query_engine/
COPY src/tools/ ./src/tools/
COPY src/state/ ./src/state/

RUN mkdir -p /app/logs && \
    chown -R queryuser:queryuser /app

USER queryuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

EXPOSE 8003

CMD ["uvicorn", "src.agents.query_engine.app:app", "--host", "0.0.0.0", "--port", "8003"]
```

### 5. Report Engine Container

```dockerfile
# containers/report-engine/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies for PDF generation
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r reportuser && useradd -r -g reportuser reportuser

WORKDIR /app

COPY requirements.txt requirements-report.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r requirements-report.txt

COPY src/agents/report_engine/ ./src/agents/report_engine/
COPY src/templates/ ./src/templates/
COPY src/state/ ./src/state/

RUN mkdir -p /app/logs /app/reports /app/templates && \
    chown -R reportuser:reportuser /app

USER reportuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1

EXPOSE 8004

CMD ["uvicorn", "src.agents.report_engine.app:app", "--host", "0.0.0.0", "--port", "8004"]
```

## Infrastructure Containers

### 1. Database Container (PostgreSQL)

```dockerfile
# containers/database/Dockerfile
FROM postgres:15-alpine

# Create non-root user
RUN addgroup -g 999 postgres && \
    adduser -u 999 -G postgres -s /bin/sh -D postgres

# Set environment variables
ENV POSTGRES_DB=bettafish \
    POSTGRES_USER=postgres \
    POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password

# Copy initialization scripts
COPY init-scripts/ /docker-entrypoint-initdb.d/
COPY schema/ /schema/

# Set permissions
RUN chown -R postgres:postgres /docker-entrypoint-initdb.d /schema

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
    CMD pg_isready -U postgres -d bettafish

EXPOSE 5432

USER postgres
```

### 2. Redis Container

```dockerfile
# containers/redis/Dockerfile
FROM redis:7-alpine

# Create non-root user
RUN addgroup -g 999 redis && \
    adduser -u 999 -G redis -s /bin/sh -D redis

# Copy Redis configuration
COPY redis.conf /usr/local/etc/redis/redis.conf

# Set permissions
RUN chown -R redis:redis /usr/local/etc/redis

# Health check
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD redis-cli ping || exit 1

EXPOSE 6379

USER redis

CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
```

### 3. Nginx Load Balancer

```dockerfile
# containers/nginx/Dockerfile
FROM nginx:alpine

# Remove default configuration
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom configuration
COPY nginx.conf /etc/nginx/nginx.conf
COPY conf.d/ /etc/nginx/conf.d/

# Create directories for logs and temp files
RUN mkdir -p /var/log/nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx /var/cache/nginx

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
```

## Docker Compose Configuration

### Development Environment

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  # API Gateway
  api-gateway:
    build:
      context: .
      dockerfile: containers/api-gateway/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/bettafish
      - REDIS_URL=redis://redis:6379/0
      - INSIGHT_ENGINE_URL=http://insight-engine:8001
      - MEDIA_ENGINE_URL=http://media-engine:8002
      - QUERY_ENGINE_URL=http://query-engine:8003
      - REPORT_ENGINE_URL=http://report-engine:8004
      - LOG_LEVEL=DEBUG
    volumes:
      - ./src:/app/src
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - bettafish-network

  # Insight Engine
  insight-engine:
    build:
      context: .
      dockerfile: containers/insight-engine/Dockerfile
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/bettafish
      - REDIS_URL=redis://redis:6379/1
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - LOG_LEVEL=DEBUG
    volumes:
      - ./src/agents/insight_engine:/app/src/agents/insight_engine
      - ./models:/app/models
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - bettafish-network

  # Media Engine
  media-engine:
    build:
      context: .
      dockerfile: containers/media-engine/Dockerfile
    ports:
      - "8002:8002"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/bettafish
      - REDIS_URL=redis://redis:6379/2
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - LOG_LEVEL=DEBUG
    volumes:
      - ./src/agents/media_engine:/app/src/agents/media_engine
      - ./media:/app/media
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - bettafish-network

  # Query Engine
  query-engine:
    build:
      context: .
      dockerfile: containers/query-engine/Dockerfile
    ports:
      - "8003:8003"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/bettafish
      - REDIS_URL=redis://redis:6379/3
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - LOG_LEVEL=DEBUG
    volumes:
      - ./src/agents/query_engine:/app/src/agents/query_engine
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - bettafish-network

  # Report Engine
  report-engine:
    build:
      context: .
      dockerfile: containers/report-engine/Dockerfile
    ports:
      - "8004:8004"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/bettafish
      - REDIS_URL=redis://redis:6379/4
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LOG_LEVEL=DEBUG
    volumes:
      - ./src/agents/report_engine:/app/src/agents/report_engine
      - ./templates:/app/templates
      - ./reports:/app/reports
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - bettafish-network

  # PostgreSQL Database
  postgres:
    build:
      context: .
      dockerfile: containers/database/Dockerfile
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=bettafish
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./schema:/schema
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d bettafish"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - bettafish-network

  # Redis Cache
  redis:
    build:
      context: .
      dockerfile: containers/redis/Dockerfile
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    restart: unless-stopped
    networks:
      - bettafish-network

  # Nginx Load Balancer
  nginx:
    build:
      context: .
      dockerfile: containers/nginx/Dockerfile
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d
      - ./ssl:/etc/nginx/ssl
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - api-gateway
    restart: unless-stopped
    networks:
      - bettafish-network

volumes:
  postgres_data:
  redis_data:

networks:
  bettafish-network:
    driver: bridge
```

### Production Environment

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  # API Gateway (with scaling)
  api-gateway:
    build:
      context: .
      dockerfile: containers/api-gateway/Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - INSIGHT_ENGINE_URL=http://insight-engine:8001
      - MEDIA_ENGINE_URL=http://media-engine:8002
      - QUERY_ENGINE_URL=http://query-engine:8003
      - REPORT_ENGINE_URL=http://report-engine:8004
      - LOG_LEVEL=INFO
      - SENTRY_DSN=${SENTRY_DSN}
    volumes:
      - logs:/app/logs
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - bettafish-network

  # Insight Engine (with scaling)
  insight-engine:
    build:
      context: .
      dockerfile: containers/insight-engine/Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - LOG_LEVEL=INFO
    volumes:
      - models:/app/models
      - logs:/app/logs
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - bettafish-network

  # Media Engine
  media-engine:
    build:
      context: .
      dockerfile: containers/media-engine/Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - LOG_LEVEL=INFO
    volumes:
      - media:/app/media
      - logs:/app/logs
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.5'
          memory: 1.5G
        reservations:
          cpus: '0.75'
          memory: 768M
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - bettafish-network

  # Query Engine
  query-engine:
    build:
      context: .
      dockerfile: containers/query-engine/Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - LOG_LEVEL=INFO
    volumes:
      - logs:/app/logs
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - bettafish-network

  # Report Engine
  report-engine:
    build:
      context: .
      dockerfile: containers/report-engine/Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LOG_LEVEL=INFO
    volumes:
      - templates:/app/templates
      - reports:/app/reports
      - logs:/app/logs
    deploy:
      replicas: 1
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - bettafish-network

  # PostgreSQL Database
  postgres:
    build:
      context: .
      dockerfile: containers/database/Dockerfile
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    secrets:
      - postgres_password
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - bettafish-network

  # Redis Cache
  redis:
    build:
      context: .
      dockerfile: containers/redis/Dockerfile
    volumes:
      - redis_data:/data
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    restart: unless-stopped
    networks:
      - bettafish-network

  # Nginx Load Balancer
  nginx:
    build:
      context: .
      dockerfile: containers/nginx/Dockerfile
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ssl:/etc/nginx/ssl:ro
      - logs/nginx:/var/log/nginx
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.25'
          memory: 128M
    depends_on:
      - api-gateway
    restart: unless-stopped
    networks:
      - bettafish-network

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  models:
    driver: local
  media:
    driver: local
  templates:
    driver: local
  reports:
    driver: local
  logs:
    driver: local
  ssl:
    driver: local

networks:
  bettafish-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

## Container Orchestration

### Kubernetes Deployment

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: bettafish
  labels:
    name: bettafish

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bettafish-config
  namespace: bettafish
data:
  LOG_LEVEL: "INFO"
  REDIS_URL: "redis://redis-service:6379/0"
  INSIGHT_ENGINE_URL: "http://insight-engine-service:8001"
  MEDIA_ENGINE_URL: "http://media-engine-service:8002"
  QUERY_ENGINE_URL: "http://query-engine-service:8003"
  REPORT_ENGINE_URL: "http://report-engine-service:8004"

---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: bettafish-secrets
  namespace: bettafish
type: Opaque
data:
  DATABASE_URL: <base64-encoded-database-url>
  OPENAI_API_KEY: <base64-encoded-openai-key>
  TAVILY_API_KEY: <base64-encoded-tavily-key>

---
# k8s/api-gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: bettafish
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
      - name: api-gateway
        image: bettafish/api-gateway:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: bettafish-secrets
              key: DATABASE_URL
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: bettafish-secrets
              key: OPENAI_API_KEY
        envFrom:
        - configMapRef:
            name: bettafish-config
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
# k8s/api-gateway-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api-gateway-service
  namespace: bettafish
spec:
  selector:
    app: api-gateway
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
# k8s/insight-engine-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: insight-engine
  namespace: bettafish
spec:
  replicas: 2
  selector:
    matchLabels:
      app: insight-engine
  template:
    metadata:
      labels:
        app: insight-engine
    spec:
      containers:
      - name: insight-engine
        image: bettafish/insight-engine:latest
        ports:
        - containerPort: 8001
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: bettafish-secrets
              key: DATABASE_URL
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: bettafish-secrets
              key: OPENAI_API_KEY
        envFrom:
        - configMapRef:
            name: bettafish-config
        resources:
          requests:
            memory: "1Gi"
            cpu: "1000m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 60
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 10
          periodSeconds: 5

---
# k8s/insight-engine-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: insight-engine-service
  namespace: bettafish
spec:
  selector:
    app: insight-engine
  ports:
  - protocol: TCP
    port: 8001
    targetPort: 8001
  type: ClusterIP

---
# k8s/postgres-deployment.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: bettafish
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: bettafish
        - name: POSTGRES_USER
          value: postgres
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: bettafish-secrets
              key: POSTGRES_PASSWORD
        resources:
          requests:
            memory: "1Gi"
            cpu: "1000m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        livenessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - postgres
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - postgres
          initialDelaySeconds: 5
          periodSeconds: 5
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi

---
# k8s/postgres-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: bettafish
spec:
  selector:
    app: postgres
  ports:
  - protocol: TCP
    port: 5432
    targetPort: 5432
  type: ClusterIP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bettafish-ingress
  namespace: bettafish
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - api.bettafish.example.com
    secretName: bettafish-tls
  rules:
  - host: api.bettafish.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-gateway-service
            port:
              number: 80
```

## Container Security

### Security Best Practices

1. **Minimal Base Images**: Use Alpine or slim variants
2. **Non-Root Users**: Run all containers as non-root
3. **Secrets Management**: Use Docker secrets or Kubernetes secrets
4. **Network Segmentation**: Isolate containers in separate networks
5. **Resource Limits**: Prevent resource exhaustion attacks
6. **Image Scanning**: Regular vulnerability scanning
7. **Immutable Infrastructure**: Rebuild rather than update

### Security Configuration

```dockerfile
# Example security-hardened Dockerfile
FROM python:3.11-slim as base

# Security updates
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create non-root user with limited privileges
RUN groupadd -r -g 1001 appuser && \
    useradd -r -u 1001 -g appuser -d /app -s /sbin/nologin appuser

# Set secure permissions
WORKDIR /app
COPY --chown=appuser:appuser . .

# Remove unnecessary packages
RUN apt-get purge -y --auto-remove && \
    apt-get clean

# Health check as non-root user
USER appuser
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1
```

This container architecture provides a comprehensive, scalable, and secure foundation for deploying the modernized BettaFish system across different environments.