# Explanation Service - Deployment Documentation

## Overview
The Explanation Service is a FastAPI-based microservice that generates AI-powered risk explanations for government procurement transactions. It uses Groq for primary LLM inference with OpenAI fallback, includes automatic validation and regeneration, and provides a comprehensive admin console.

## Architecture

```
                    Explanation Service
                       Port: 8017

  Auth Routes       Explanation Routes       Admin Routes
  /auth/*           /api/v1/explanation/*    /api/admin/*

                    ExplanationService
         (cache -> LLM -> validate -> regenerate -> fallback)

                    Redis Cache    PostgreSQL    Groq/OpenAI
```

## Prerequisites

- Docker & Docker Compose
- PostgreSQL 15+ with pgvector extension
- Redis 7+
- Groq API key (primary LLM)
- OpenAI API key (fallback LLM)
- Python 3.11+

## Environment Variables

### Required
```bash
EXPLANATION_SERVICE_NAME=explanation-svc
EXPLANATION_PORT=8017
EXPLANATION_HOST=0.0.0.0

# Database
EXPLANATION_DB_HOST=postgres
EXPLANATION_DB_PORT=5432
EXPLANATION_DB_NAME=govspend_explanations
EXPLANATION_DB_USER=explanation_user
EXPLANATION_DB_PASSWORD=<secure_password>

# Redis
EXPLANATION_REDIS_HOST=redis
EXPLANATION_REDIS_PORT=6379
EXPLANATION_REDIS_DB=0
EXPLANATION_REDIS_PASSWORD=<secure_password>

# LLM
EXPLANATION_LLM_PROVIDER=groq
EXPLANATION_LLM_MODEL=mixtral-8x7b-32768
EXPLANATION_GROQ_API_KEY=<groq_api_key>
EXPLANATION_OPENAI_API_KEY=<openai_api_key>
```

### Optional
```bash
# Logging
EXPLANATION_LOG_LEVEL=INFO
EXPLANATION_LOG_FORMAT=json

# CORS
EXPLANATION_CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Validation
EXPLANATION_VALIDATION_STRICTNESS=strict
EXPLANATION_REQUIRE_CITATIONS=true
EXPLANATION_MIN_GROUNDING_SCORE=0.7
EXPLANATION_MIN_CONFIDENCE_THRESHOLD=0.5

# Regeneration
EXPLANATION_MAX_REGENERATION_ATTEMPTS=2

# Fallback
EXPLANATION_FALLBACK_ENABLED=true

# Cache
EXPLANATION_CACHE_ENABLED=true
EXPLANATION_CACHE_TTL_SECONDS=3600

# Performance
EXPLANATION_TIMEOUT_SECONDS=60
EXPLANATION_MAX_RETRIES=3
EXPLANATION_RETRY_DELAY_SECONDS=2.0

# Security
EXPLANATION_JWT_SECRET=<jwt_secret>
EXPLANATION_HMAC_KEY=<hmac_key>

# Rate Limiting
EXPLANATION_RATE_LIMIT_MAX_REQUESTS=200
EXPLANATION_RATE_LIMIT_WINDOW_SECONDS=60
```

## Docker Deployment

### Build Image
```bash
cd services/explanation-svc
docker build -t govspend/explanation-svc:1.0.0 .
```

### Docker Compose
```yaml
services:
  explanation-svc:
    image: govspend/explanation-svc:1.0.0
    ports:
      - "8017:8017"
    environment:
      - EXPLANATION_DB_HOST=postgres
      - EXPLANATION_REDIS_HOST=redis
      - EXPLANATION_GROQ_API_KEY=${GROQ_API_KEY}
      - EXPLANATION_OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8017/health').raise_for_status()"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
```

## Kubernetes Deployment

### Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: explanation-svc
  namespace: govspend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: explanation-svc
  template:
    metadata:
      labels:
        app: explanation-svc
    spec:
      containers:
      - name: explanation-svc
        image: govspend/explanation-svc:1.0.0
        ports:
        - containerPort: 8017
        env:
        - name: EXPLANATION_ENVIRONMENT
          value: "production"
        - name: EXPLANATION_DB_HOST
          value: "postgres-govspend"
        - name: EXPLANATION_REDIS_HOST
          value: "redis-master"
        - name: EXPLANATION_GROQ_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets
              key: groq-api-key
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 1000m
            memory: 2Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8017
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8017
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Health Checks

```bash
# Liveness/Readiness
curl http://localhost:8017/health

# Detailed status
curl http://localhost:8017/api/v1/status
```

## Scaling Considerations

### Horizontal Scaling
- Deploy multiple replicas behind a load balancer
- Use Redis for shared cache across instances
- Ensure database connection pool is sized appropriately

### Database Pool Sizing
```python
# For N replicas with M max connections each:
# PostgreSQL max_connections should be >= N * M + 10 (reserved)
# Default: pool_size=5, max_overflow=10 per replica
# With 3 replicas: need 45+ connections
```

### Cache Optimization
- Enable Redis clustering for high availability
- Use cache warming for frequently accessed explanations
- Monitor cache hit rates via /api/admin/cache/stats

## Monitoring

### Prometheus Metrics
Available at /metrics:
- explanation_requests_total
- explanation_request_duration_seconds
- explanation_cache_hits_total
- explanation_llm_errors_total
- explanation_validation_failures_total

### Key Metrics
- Request latency (p50, p95, p99)
- Cache hit rate
- LLM provider availability
- Validation pass rate
- Regeneration success rate
- Error rate by endpoint

## Backup and Recovery

### PostgreSQL
```bash
pg_dump -h postgres -U explanation_user govspend_explanations > backup.sql
psql -h postgres -U explanation_user govspend_explanations < backup.sql
```

### Redis
```bash
redis-cli BGSAVE
```

## Security

- Run behind internal load balancer
- Use TLS termination at ingress
- Restrict database and Redis access to service network
- Use Docker secrets or Kubernetes secrets for API keys
- Rotate API keys regularly
