# Explanation Validator Service - Deployment Documentation

## Overview
The Explanation Validator Service validates AI-generated explanations for grounding, citations, and schema compliance. It ensures 100% grounding of claims to evidence or policy references.

## Architecture

```
                    Validator Service
                       Port: 8018

  SchemaValidator    CitationValidator    GroundingService
  MaskingService      RephraserService

  PostgreSQL (validations table)
  Redis (optional cache)
```

## Environment Variables

### Required
```bash
VALIDATOR_SERVICE_NAME=explanation-validator-svc
VALIDATOR_PORT=8018
VALIDATOR_HOST=0.0.0.0

VALIDATOR_DB_HOST=postgres
VALIDATOR_DB_PORT=5432
VALIDATOR_DB_NAME=govspend
VALIDATOR_DB_USER=validator_user
VALIDATOR_DB_PASSWORD=<secure_password>

VALIDATOR_REDIS_HOST=redis
VALIDATOR_REDIS_PORT=6379
VALIDATOR_REDIS_DB=0
```

### Optional
```bash
VALIDATOR_LOG_LEVEL=INFO
VALIDATOR_LOG_FORMAT=json
VALIDATOR_ENVIRONMENT=production

VALIDATOR_REQUIRE_100_PERCENT_GROUNDING=true
VALIDATOR_STRICT_CITATION_CHECK=true
VALIDATOR_MIN_GROUNDING_SCORE=1.0
VALIDATOR_ALLOWED_MISSING_CITATIONS=0

VALIDATOR_MASK_UNGROUNDED_CLAIMS=true
VALIDATOR_MASK_MARKER=[UNCITED]
VALIDATOR_REPHRASE_UNGROUNDED=true

VALIDATOR_GROQ_API_KEY=<groq_api_key>
VALIDATOR_OPENAI_API_KEY=<openai_api_key>
VALIDATOR_LLM_MODEL=mixtral-8x7b-32768

VALIDATOR_RATE_LIMIT_MAX_REQUESTS=100
VALIDATOR_RATE_LIMIT_WINDOW_SECONDS=60
```

## Health Checks

```bash
curl http://localhost:8018/health
curl http://localhost:8018/health/detailed
```

## Metrics

Prometheus metrics available at /metrics:
- validator_requests_total
- validator_request_duration_seconds
- validator_active_connections
- validator_grounding_score
