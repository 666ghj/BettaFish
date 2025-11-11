# Monitoring and Observability

## Overview

This document defines the comprehensive monitoring and observability strategy for the modernized BettaFish system, ensuring system health, performance tracking, and proactive issue detection.

## Monitoring Philosophy

### Core Principles
1. **Observability-First Design**: Build monitoring into system architecture from the start
2. **Multi-Layer Monitoring**: Infrastructure, application, and business metrics
3. **Proactive Alerting**: Detect issues before they impact users
4. **Data-Driven Decisions**: Use metrics for optimization and capacity planning
5. **Unified Monitoring**: Single pane of glass for all system observability

### Monitoring Pillars
```
┌─────────────────────────────────────────────────────────────┐
│                    Observability                          │
├─────────────────┬─────────────────┬─────────────────────┤
│   Metrics       │    Logs        │     Tracing         │
│ (What/How Much)│ (What Happened)│ (Where/Why)        │
└─────────────────┴─────────────────┴─────────────────────┘
```

## Metrics Collection

### Infrastructure Metrics

#### System Metrics
```yaml
# CPU Metrics
cpu_metrics:
  - name: "cpu_utilization"
    type: "gauge"
    unit: "percent"
    labels: ["instance", "service", "availability_zone"]
    collection_interval: 30
    
  - name: "cpu_load_average"
    type: "gauge"
    unit: "count"
    labels: ["instance", "period"]  # 1m, 5m, 15m
    collection_interval: 60

# Memory Metrics
memory_metrics:
  - name: "memory_utilization"
    type: "gauge"
    unit: "percent"
    labels: ["instance", "service"]
    collection_interval: 30
    
  - name: "memory_available"
    type: "gauge"
    unit: "bytes"
    labels: ["instance"]
    collection_interval: 30

# Disk Metrics
disk_metrics:
  - name: "disk_utilization"
    type: "gauge"
    unit: "percent"
    labels: ["instance", "device", "mount_point"]
    collection_interval: 60
    
  - name: "disk_io_operations"
    type: "counter"
    unit: "operations"
    labels: ["instance", "device", "operation"]  # read/write
    collection_interval: 30

# Network Metrics
network_metrics:
  - name: "network_bytes_transmitted"
    type: "counter"
    unit: "bytes"
    labels: ["instance", "interface"]
    collection_interval: 30
    
  - name: "network_packets_dropped"
    type: "counter"
    unit: "packets"
    labels: ["instance", "interface"]
    collection_interval: 30
```

#### Container Metrics
```yaml
# Kubernetes Metrics
kubernetes_metrics:
  - name: "container_cpu_usage_seconds_total"
    type: "counter"
    unit: "seconds"
    labels: ["namespace", "pod", "container"]
    
  - name: "container_memory_working_set_bytes"
    type: "gauge"
    unit: "bytes"
    labels: ["namespace", "pod", "container"]
    
  - name: "container_network_receive_bytes_total"
    type: "counter"
    unit: "bytes"
    labels: ["namespace", "pod", "interface"]
    
  - name: "container_fs_reads_total"
    type: "counter"
    unit: "operations"
    labels: ["namespace", "pod", "container", "device"]
```

### Application Metrics

#### API Gateway Metrics
```python
# Custom Application Metrics
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Request Counters
REQUEST_COUNT = Counter(
    'bettafish_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status_code', 'agent']
)

# Response Time Histograms
REQUEST_DURATION = Histogram(
    'bettafish_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint', 'agent'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Active Queries Gauge
ACTIVE_QUERIES = Gauge(
    'bettafish_active_queries',
    'Number of currently active queries',
    ['agent']
)

# Agent Processing Metrics
AGENT_PROCESSING_TIME = Histogram(
    'bettafish_agent_processing_duration_seconds',
    'Agent processing duration in seconds',
    ['agent', 'operation'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0]
)

# Query Success Rate
QUERY_SUCCESS_RATE = Gauge(
    'bettafish_query_success_rate',
    'Query success rate percentage',
    ['agent', 'time_window']  # 1m, 5m, 15m, 1h
)

# Token Usage
TOKEN_USAGE = Counter(
    'bettafish_tokens_used_total',
    'Total tokens used',
    ['agent', 'model', 'operation']
)

# Data Processing
DATA_PROCESSED = Counter(
    'bettafish_data_processed_total',
    'Total data points processed',
    ['agent', 'data_type', 'source']
)
```

#### Agent-Specific Metrics
```python
# Insight Engine Metrics
class InsightEngineMetrics:
    def __init__(self):
        self.sentiment_analysis_duration = Histogram(
            'insight_engine_sentiment_analysis_duration_seconds',
            'Sentiment analysis processing time',
            ['model', 'data_source']
        )
        
        self.sentiment_confidence = Histogram(
            'insight_engine_sentiment_confidence',
            'Sentiment analysis confidence scores',
            ['sentiment', 'data_source']
        )
        
        self.keyword_extraction_count = Counter(
            'insight_engine_keywords_extracted_total',
            'Total keywords extracted',
            ['query_type', 'language']
        )

# Media Engine Metrics
class MediaEngineMetrics:
    def __init__(self):
        self.media_processing_duration = Histogram(
            'media_engine_processing_duration_seconds',
            'Media content processing time',
            ['content_type', 'platform']
        )
        
        self.viral_content_detected = Counter(
            'media_engine_viral_content_detected_total',
            'Viral content detections',
            ['platform', 'content_type']
        )
        
        self.content_analysis_accuracy = Gauge(
            'media_engine_content_analysis_accuracy',
            'Content analysis accuracy percentage',
            ['analysis_type']
        )

# Query Engine Metrics
class QueryEngineMetrics:
    def __init__(self):
        self.search_duration = Histogram(
            'query_engine_search_duration_seconds',
            'Search operation duration',
            ['search_type', 'source']
        )
        
        self.search_results_count = Histogram(
            'query_engine_search_results_count',
            'Number of search results',
            ['search_type', 'source']
        )
        
        self.query_success_rate = Gauge(
            'query_engine_success_rate',
            'Query success rate',
            ['search_type', 'time_window']
        )
```

### Business Metrics

#### User Engagement Metrics
```python
# Business Metrics
class BusinessMetrics:
    def __init__(self):
        # User Activity
        self.daily_active_users = Gauge(
            'bettafish_daily_active_users',
            'Number of daily active users'
        )
        
        self.queries_per_user = Histogram(
            'bettafish_queries_per_user_daily',
            'Queries per user per day',
            buckets=[1, 5, 10, 25, 50, 100]
        )
        
        # Feature Usage
        self.feature_usage = Counter(
            'bettafish_feature_usage_total',
            'Feature usage count',
            ['feature', 'user_type']
        )
        
        # Performance
        self.query_satisfaction = Gauge(
            'bettafish_query_satisfaction_score',
            'User satisfaction score for queries',
            ['query_type', 'time_window']
        )
```

## Logging Strategy

### Log Hierarchy
```
┌─────────────────────────────────────────────────────────────┐
│                    Log Levels                             │
├─────────────────┬─────────────────┬─────────────────────┤
│   ERROR         │    WARN        │     INFO            │
│ (Critical Issues)│ (Potential Issues)│ (General Info)     │
├─────────────────┼─────────────────┼─────────────────────┤
│   DEBUG         │    TRACE       │                     │
│ (Detailed Debug)│ (Full Trace)   │                     │
└─────────────────┴─────────────────┴─────────────────────┘
```

### Structured Logging Format
```python
import json
import logging
from datetime import datetime
from typing import Dict, Any

class StructuredLogger:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        
    def _log(self, level: str, message: str, **kwargs):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "service": self.service_name,
            "message": message,
            "trace_id": kwargs.get("trace_id"),
            "span_id": kwargs.get("span_id"),
            "user_id": kwargs.get("user_id"),
            "query_id": kwargs.get("query_id"),
            "agent": kwargs.get("agent"),
            "duration_ms": kwargs.get("duration_ms"),
            "error_code": kwargs.get("error_code"),
            "metadata": {k: v for k, v in kwargs.items() 
                        if k not in ["trace_id", "span_id", "user_id", 
                                   "query_id", "agent", "duration_ms", "error_code"]}
        }
        
        getattr(self.logger, level.lower())(json.dumps(log_entry))
    
    def info(self, message: str, **kwargs):
        self._log("INFO", message, **kwargs)
    
    def warn(self, message: str, **kwargs):
        self._log("WARN", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log("ERROR", message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self._log("DEBUG", message, **kwargs)

# Usage Example
logger = StructuredLogger("insight-engine")

logger.info(
    "Query processing started",
    query_id="q123",
    user_id="u456",
    agent="insight-engine",
    query_type="sentiment_analysis"
)

logger.error(
    "API call failed",
    query_id="q123",
    error_code="TAVILY_RATE_LIMIT",
    duration_ms=5000,
    retry_count=3
)
```

### Log Categories
```yaml
# Application Logs
application_logs:
  level: "INFO"
  format: "structured_json"
  retention: 30  # days
  fields:
    - timestamp
    - level
    - service
    - message
    - trace_id
    - user_id
    - query_id
    - agent
    - duration_ms

# Access Logs
access_logs:
  level: "INFO"
  format: "nginx_combined"
  retention: 90  # days
  fields:
    - timestamp
    - remote_addr
    - method
    - uri
    - status
    - bytes_sent
    - user_agent
    - request_time
    - upstream_addr

# Error Logs
error_logs:
  level: "ERROR"
  format: "structured_json"
  retention: 90  # days
  fields:
    - timestamp
    - level
    - service
    - message
    - error_code
    - stack_trace
    - trace_id
    - user_id
    - query_id

# Audit Logs
audit_logs:
  level: "INFO"
  format: "structured_json"
  retention: 2555  # 7 years
  fields:
    - timestamp
    - action
    - user_id
    - resource
    - result
    - ip_address
    - user_agent
```

## Distributed Tracing

### OpenTelemetry Configuration
```python
from opentelemetry import trace, baggage
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

class TracingSetup:
    def __init__(self, service_name: str, jaeger_endpoint: str):
        self.service_name = service_name
        self.jaeger_endpoint = jaeger_endpoint
        self.setup_tracing()
    
    def setup_tracing(self):
        # Set up tracer provider
        trace.set_tracer_provider(TracerProvider())
        tracer = trace.get_tracer(__name__)
        
        # Set up Jaeger exporter
        jaeger_exporter = JaegerExporter(
            endpoint=self.jaeger_endpoint,
            collector_endpoint=self.jaeger_endpoint
        )
        
        # Add span processor
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Instrument libraries
        FastAPIInstrumentor.instrument()
        RequestsInstrumentor.instrument()
        SQLAlchemyInstrumentor.instrument()
        
        return tracer

# Usage in Application
tracer = TracingSetup("api-gateway", "http://jaeger:14268/api/traces").setup_tracing()

@tracer.start_as_current_span("process_query")
async def process_query(query: str, user_id: str):
    # Add baggage for trace context
    baggage.set_baggage("user_id", user_id)
    baggage.set_baggage("query", query)
    
    with tracer.start_as_current_span("validate_input"):
        # Validation logic
        pass
    
    with tracer.start_as_current_span("call_agents"):
        # Agent coordination logic
        pass
    
    with tracer.start_as_current_span("generate_response"):
        # Response generation
        pass
```

### Span Attributes
```python
# Standard Span Attributes
SPAN_ATTRIBUTES = {
    # General
    "service.name": "bettafish",
    "service.version": "2.0.0",
    "deployment.environment": "production",
    
    # HTTP
    "http.method": "GET",
    "http.url": "/api/v1/query",
    "http.status_code": "200",
    "http.user_agent": "Mozilla/5.0...",
    
    # Database
    "db.system": "postgresql",
    "db.name": "bettafish",
    "db.operation": "SELECT",
    "db.statement": "SELECT * FROM queries WHERE id = ?",
    
    # Agent Specific
    "agent.name": "insight-engine",
    "agent.operation": "sentiment_analysis",
    "agent.model": "gpt-4o-mini",
    "agent.tokens_used": "150",
    
    # Business
    "business.query_type": "sentiment_analysis",
    "business.user_tier": "premium",
    "business.feature": "real_time_analysis"
}
```

## Alerting Strategy

### Alert Hierarchy
```yaml
# Alert Severity Levels
alert_severity:
  critical:
    description: "Service down or major functionality broken"
    response_time: "5 minutes"
    escalation: "immediate"
    channels: ["pagerduty", "slack", "email"]
    
  high:
    description: "Significant degradation or partial outage"
    response_time: "15 minutes"
    escalation: "30 minutes"
    channels: ["slack", "email"]
    
  medium:
    description: "Minor issues or performance degradation"
    response_time: "1 hour"
    escalation: "4 hours"
    channels: ["slack"]
    
  low:
    description: "Informational or minor issues"
    response_time: "4 hours"
    escalation: "24 hours"
    channels: ["email"]
```

### Alert Rules
```yaml
# Infrastructure Alerts
infrastructure_alerts:
  - name: "HighCPUUtilization"
    condition: "cpu_utilization > 90"
    duration: "5m"
    severity: "high"
    labels:
      team: "infrastructure"
      service: "compute"
    annotations:
      summary: "High CPU utilization on {{ $labels.instance }}"
      description: "CPU utilization is {{ $value }}% for more than 5 minutes"
      
  - name: "HighMemoryUtilization"
    condition: "memory_utilization > 85"
    duration: "5m"
    severity: "high"
    labels:
      team: "infrastructure"
      service: "compute"
    annotations:
      summary: "High memory utilization on {{ $labels.instance }}"
      description: "Memory utilization is {{ $value }}% for more than 5 minutes"
      
  - name: "DiskSpaceLow"
    condition: "disk_utilization > 80"
    duration: "10m"
    severity: "medium"
    labels:
      team: "infrastructure"
      service: "storage"
    annotations:
      summary: "Low disk space on {{ $labels.instance }}"
      description: "Disk utilization is {{ $value }}% on {{ $labels.mount_point }}"

# Application Alerts
application_alerts:
  - name: "HighErrorRate"
    condition: "rate(bettafish_requests_total{status_code=~'5..'}[5m]) / rate(bettafish_requests_total[5m]) > 0.05"
    duration: "2m"
    severity: "critical"
    labels:
      team: "application"
      service: "api-gateway"
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value | humanizePercentage }} for the last 5 minutes"
      
  - name: "HighResponseTime"
    condition: "histogram_quantile(0.95, rate(bettafish_request_duration_seconds_bucket[5m])) > 5"
    duration: "5m"
    severity: "high"
    labels:
      team: "application"
      service: "api-gateway"
    annotations:
      summary: "High response time detected"
      description: "95th percentile response time is {{ $value }}s"
      
  - name: "AgentDown"
    condition: "up{job=~'bettafish-.*'} == 0"
    duration: "1m"
    severity: "critical"
    labels:
      team: "application"
      service: "agents"
    annotations:
      summary: "Agent {{ $labels.job }} is down"
      description: "Agent {{ $labels.job }} has been down for more than 1 minute"

# Business Alerts
business_alerts:
  - name: "LowQuerySuccessRate"
    condition: "bettafish_query_success_rate < 0.95"
    duration: "10m"
    severity: "high"
    labels:
      team: "business"
      service: "query-processing"
    annotations:
      summary: "Low query success rate"
      description: "Query success rate is {{ $value | humanizePercentage }} for {{ $labels.time_window }}"
      
  - name: "HighTokenUsage"
    condition: "rate(bettafish_tokens_used_total[1h]) > 10000"
    duration: "15m"
    severity: "medium"
    labels:
      team: "business"
      service: "cost-management"
    annotations:
      summary: "High token usage detected"
      description: "Token usage rate is {{ $value }} tokens/hour"
```

### Alert Management
```python
# Alert Manager Configuration
alertmanager_config = """
global:
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'alerts@bettafish.com'
  
route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'default'
  routes:
  - match:
      severity: critical
    receiver: 'critical-alerts'
  - match:
      severity: high
    receiver: 'high-alerts'
  - match:
      severity: medium
    receiver: 'medium-alerts'
  - match:
      severity: low
    receiver: 'low-alerts'

receivers:
- name: 'default'
  email_configs:
  - to: 'team@bettafish.com'
    subject: '[BettaFish] {{ .GroupLabels.alertname }}'
    
- name: 'critical-alerts'
  pagerduty_configs:
  - service_key: 'YOUR_PAGERDUTY_KEY'
    description: '{{ .GroupLabels.alertname }}: {{ .GroupAnnotations.summary }}'
  slack_configs:
  - api_url: 'YOUR_SLACK_WEBHOOK'
    channel: '#alerts-critical'
    title: '🚨 Critical Alert: {{ .GroupLabels.alertname }}'
    text: '{{ .GroupAnnotations.description }}'
    
- name: 'high-alerts'
  slack_configs:
  - api_url: 'YOUR_SLACK_WEBHOOK'
    channel: '#alerts-high'
    title: '⚠️ High Alert: {{ .GroupLabels.alertname }}'
    text: '{{ .GroupAnnotations.description }}'
  email_configs:
  - to: 'team@bettafish.com'
    subject: '[BettaFish] High Alert: {{ .GroupLabels.alertname }}'
    
- name: 'medium-alerts'
  slack_configs:
  - api_url: 'YOUR_SLACK_WEBHOOK'
    channel: '#alerts-medium'
    title: '⚡ Medium Alert: {{ .GroupLabels.alertname }}'
    text: '{{ .GroupAnnotations.description }}'
    
- name: 'low-alerts'
  email_configs:
  - to: 'team@bettafish.com'
    subject: '[BettaFish] Low Alert: {{ .GroupLabels.alertname }}'
"""
```

## Dashboard Design

### System Overview Dashboard
```yaml
# Grafana Dashboard Configuration
dashboard_overview:
  title: "BettaFish System Overview"
  panels:
    # System Health
    - title: "System Health"
      type: "stat"
      targets:
        - expr: "up{job=~'bettafish-.*'}"
          legendFormat: "{{ job }}"
      thresholds:
        - color: "red"
          value: 0
        - color: "green"
          value: 1
          
    # Request Rate
    - title: "Request Rate"
      type: "graph"
      targets:
        - expr: "rate(bettafish_requests_total[5m])"
          legendFormat: "{{ method }} {{ endpoint }}"
      yAxes:
        - unit: "reqps"
        
    # Response Time
    - title: "Response Time (95th percentile)"
      type: "graph"
      targets:
        - expr: "histogram_quantile(0.95, rate(bettafish_request_duration_seconds_bucket[5m]))"
          legendFormat: "{{ endpoint }}"
      yAxes:
        - unit: "seconds"
        
    # Error Rate
    - title: "Error Rate"
      type: "graph"
      targets:
        - expr: "rate(bettafish_requests_total{status_code=~'5..'}[5m]) / rate(bettafish_requests_total[5m])"
          legendFormat: "Error Rate"
      yAxes:
        - unit: "percent"
        - max: 1
        
    # Active Queries
    - title: "Active Queries"
      type: "stat"
      targets:
        - expr: "sum(bettafish_active_queries)"
          legendFormat: "Active Queries"
          
    # Agent Status
    - title: "Agent Status"
      type: "table"
      targets:
        - expr: "up{job=~'bettafish-.*'}"
          format: "table"
          instant: true
```

### Agent Performance Dashboard
```yaml
dashboard_agents:
  title: "Agent Performance"
  panels:
    # Agent Processing Time
    - title: "Agent Processing Time"
      type: "graph"
      targets:
        - expr: "histogram_quantile(0.95, rate(bettafish_agent_processing_duration_seconds_bucket[5m]))"
          legendFormat: "{{ agent }} {{ operation }}"
      yAxes:
        - unit: "seconds"
        
    # Query Success Rate
    - title: "Query Success Rate"
      type: "graph"
      targets:
        - expr: "bettafish_query_success_rate"
          legendFormat: "{{ agent }} ({{ time_window }})"
      yAxes:
        - unit: "percent"
        - max: 1
        
    # Token Usage
    - title: "Token Usage Rate"
      type: "graph"
      targets:
        - expr: "rate(bettafish_tokens_used_total[1h])"
          legendFormat: "{{ agent }} {{ model }}"
      yAxes:
        - unit: "tokens/hour"
        
    # Data Processed
    - title: "Data Points Processed"
      type: "graph"
      targets:
        - expr: "rate(bettafish_data_processed_total[1h])"
          legendFormat: "{{ agent }} {{ data_type }}"
      yAxes:
        - unit: "points/hour"
```

## Performance Monitoring

### Application Performance Monitoring (APM)
```python
# APM Configuration
class APMonitoring:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.setup_apm()
    
    def setup_apm(self):
        # Set up performance monitoring
        self.trace_performance_slow_queries()
        self.monitor_memory_usage()
        self.track_external_api_calls()
        self.monitor_database_performance()
    
    def trace_performance_slow_queries(self):
        """Trace slow database queries"""
        @trace.get_tracer(__name__).start_as_current_span("slow_query_detection")
        def monitor_query(query, params):
            start_time = time.time()
            try:
                result = execute_query(query, params)
                duration = time.time() - start_time
                
                if duration > 1.0:  # Slow query threshold
                    logger.warning(
                        "Slow query detected",
                        query=query,
                        duration=duration,
                        params=params
                    )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "Query failed",
                    query=query,
                    duration=duration,
                    error=str(e)
                )
                raise
        
        return monitor_query
    
    def monitor_memory_usage(self):
        """Monitor memory usage patterns"""
        import psutil
        
        def get_memory_metrics():
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss": memory_info.rss,
                "vms": memory_info.vms,
                "percent": process.memory_percent()
            }
        
        # Record metrics every 30 seconds
        while True:
            metrics = get_memory_metrics()
            
            # Send to monitoring system
            self.record_metric("memory_rss_bytes", metrics["rss"])
            self.record_metric("memory_vms_bytes", metrics["vms"])
            self.record_metric("memory_percent", metrics["percent"])
            
            time.sleep(30)
    
    def track_external_api_calls(self):
        """Track external API call performance"""
        import requests
        from requests.adapters import HTTPAdapter
        
        class MonitoringAdapter(HTTPAdapter):
            def send(self, request, **kwargs):
                start_time = time.time()
                
                try:
                    response = super().send(request, **kwargs)
                    duration = time.time() - start_time
                    
                    # Record metrics
                    self.record_metric(
                        "external_api_request_duration_seconds",
                        duration,
                        tags={
                            "url": request.url,
                            "method": request.method,
                            "status_code": response.status_code
                        }
                    )
                    
                    return response
                    
                except Exception as e:
                    duration = time.time() - start_time
                    
                    # Record error metrics
                    self.record_metric(
                        "external_api_request_errors_total",
                        1,
                        tags={
                            "url": request.url,
                            "method": request.method,
                            "error_type": type(e).__name__
                        }
                    )
                    
                    raise
        
        # Install monitoring adapter
        session = requests.Session()
        session.mount("http://", MonitoringAdapter())
        session.mount("https://", MonitoringAdapter())
        
        return session
```

## Health Checks

### Application Health Checks
```python
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

app = FastAPI()

class HealthChecker:
    def __init__(self):
        self.checks = {}
    
    def add_check(self, name: str, check_func):
        """Add a health check function"""
        self.checks[name] = check_func
    
    async def run_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                result = await check_func()
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "details": result
                }
                if not result:
                    overall_healthy = False
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e)
                }
                overall_healthy = False
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "checks": results,
            "timestamp": datetime.utcnow().isoformat()
        }

# Health check functions
health_checker = HealthChecker()

async def check_database():
    """Check database connectivity"""
    try:
        # Test database connection
        result = await database.execute("SELECT 1")
        return result[0][0] == 1
    except Exception:
        return False

async def check_redis():
    """Check Redis connectivity"""
    try:
        await redis.ping()
        return True
    except Exception:
        return False

async def check_external_apis():
    """Check external API availability"""
    try:
        # Test Tavily API
        response = await http_client.get(
            "https://api.tavily.com/health",
            timeout=5
        )
        return response.status_code == 200
    except Exception:
        return False

async def check_agent_health():
    """Check agent health"""
    try:
        # Check if agents are responding
        responses = await asyncio.gather(
            http_client.get("http://insight-engine:8001/health"),
            http_client.get("http://media-engine:8002/health"),
            http_client.get("http://query-engine:8003/health"),
            http_client.get("http://report-engine:8004/health"),
            return_exceptions=True
        )
        
        return all(isinstance(r, type(None)) or r.status_code == 200 for r in responses)
    except Exception:
        return False

# Register health checks
health_checker.add_check("database", check_database)
health_checker.add_check("redis", check_redis)
health_checker.add_check("external_apis", check_external_apis)
health_checker.add_check("agents", check_agent_health)

@app.get("/health")
async def health_check():
    """Main health check endpoint"""
    result = await health_checker.run_checks()
    
    if result["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=result)
    
    return result

@app.get("/health/ready")
async def readiness_check():
    """Readiness check for Kubernetes"""
    result = await health_checker.run_checks()
    
    # Check critical dependencies
    critical_checks = ["database", "redis"]
    for check in critical_checks:
        if result["checks"].get(check, {}).get("status") != "healthy":
            raise HTTPException(status_code=503, detail="Not ready")
    
    return {"status": "ready"}

@app.get("/health/live")
async def liveness_check():
    """Liveness check for Kubernetes"""
    return {"status": "alive"}
```

This comprehensive monitoring and observability specification ensures the modernized BettaFish system has full visibility into its operations, enabling proactive issue detection and performance optimization.