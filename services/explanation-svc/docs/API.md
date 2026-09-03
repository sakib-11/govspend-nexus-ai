# Explanation Service API Documentation

## Base URL
```
http://localhost:8017
```

## Authentication
All endpoints (except `/health` and `/`) require authentication via JWT token or session cookie.

### Login
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "auditor@example.com",
  "password": "auditor123"
}
```

**Response:**
```json
{
  "token": "<jwt_token>",
  "user": {
    "user_id": "user_123",
    "username": "auditor@example.com",
    "roles": ["auditor_level_2"],
    "permissions": ["read_cases", "approve_cases"]
  },
  "requires_mfa": false
}
```

---

## Explanation Routes

### Generate Explanation
```bash
POST /api/v1/explanation/generate
Authorization: Bearer <token>
Content-Type: application/json

{
  "case_id": "CASE-001",
  "transaction_id": "TXN-001",
  "risk_score": 0.85,
  "risk_tier": "HIGH",
  "evidence_bundle": {
    "evidence": [
      {"id": "EV-001", "type": "invoice", "description": "Invoice price 50% above market"}
    ]
  },
  "retrieved_policies": [
    {"policy_id": "GFR-4.3", "title": "Procurement Rules", "content": "Procurement at market rates"}
  ],
  "signals": [
    {"detector_type": "price_deviation", "signal_value": 0.92, "confidence": 0.95, "evidence_ids": ["EV-001"]}
  ]
}
```

**Response:**
```json
{
  "explanation_id": "exp-abc123",
  "case_id": "CASE-001",
  "transaction_id": "TXN-001",
  "summary": "This case shows significant risk indicators...",
  "confidence": 0.92,
  "grounding_score": 1.0,
  "explanations": [
    {
      "point_number": 1,
      "detector_name": "price_deviation",
      "sentence": "The invoice unit price exceeds historical market benchmarks by 50%...",
      "confidence": 0.95,
      "evidence_ids": ["EV-001"],
      "citations": [
        {
          "citation_type": "evidence",
          "reference_id": "EV-001",
          "reference_text": "Invoice price 50% above market",
          "relevance_score": 0.95
        }
      ]
    }
  ],
  "status": "validated",
  "is_fallback": false,
  "llm_model": "mixtral-8x7b-32768",
  "llm_provider": "groq"
}
```

### Get Explanation
```bash
GET /api/v1/explanation/{case_id}
Authorization: Bearer <token>
```

### Validate Explanation
```bash
POST /api/v1/explanation/validate
Authorization: Bearer <token>
Content-Type: application/json

{
  "explanation": { /* explanation JSON */ },
  "input_data": { /* original request data */ }
}
```

### Clear Cache
```bash
DELETE /api/v1/explanation/cache/{case_id}
Authorization: Bearer <token>
```
**Requires:** Admin role

---

## Case Routes

### List Cases
```bash
GET /api/cases/?tier=HIGH&status=PENDING&limit=50&offset=0
Authorization: Bearer <token>
```

### Get Case Detail
```bash
GET /api/cases/{case_id}
Authorization: Bearer <token>
```

### Perform Case Action
```bash
POST /api/cases/{case_id}/actions
Authorization: Bearer <token>
Content-Type: application/json

{
  "type": "approve",
  "comments": "Approved based on evidence"
}
```

### List Unmask Requests
```bash
GET /api/cases/unmask-requests?status=pending
Authorization: Bearer <token>
```

---

## Graph Routes

### Get Vendor Graph
```bash
GET /api/graph/vendor/{vendor_token}?depth=2
Authorization: Bearer <token>
```

### Get Case Graph
```bash
GET /api/graph/case/{case_id}
Authorization: Bearer <token>
```

### Get Graph Metadata
```bash
GET /api/graph/metadata
Authorization: Bearer <token>
```

---

## Unmask Routes

### List Unmask Requests
```bash
GET /api/unmask/requests?status_filter=pending&limit=50&offset=0
Authorization: Bearer <token>
```

### Create Unmask Request
```bash
POST /api/unmask/request
Authorization: Bearer <token>
Content-Type: application/json

{
  "case_id": "CASE-001",
  "reason": "Need access to contract terms",
  "justification": "Regulatory compliance requirement",
  "data_fields": ["contract_terms", "vendor_revenue"]
}
```

### Approve Unmask Request
```bash
POST /api/unmask/request/{request_id}/approve
Authorization: Bearer <token>
Content-Type: application/json

{
  "comments": "Approved - legitimate business reason"
}
```
**Requires:** auditor_level_2 or auditor_level_3

### Reject Unmask Request
```bash
POST /api/unmask/request/{request_id}/reject
Authorization: Bearer <token>
Content-Type: application/json

{
  "rejection_reason": "Business purpose not aligned"
}
```
**Requires:** auditor_level_2 or auditor_level_3

---

## Admin Routes

**All admin endpoints require:** `admin` or `super_admin` role

### System Health
```bash
GET /api/admin/health
Authorization: Bearer <token>
```

### Diagnostics
```bash
GET /api/admin/diagnostics
Authorization: Bearer <token>
```
**Requires:** `view_admin` permission

### User Management
```bash
# List users
GET /api/admin/users?limit=50&offset=0&role=admin

# Get user
GET /api/admin/users/{user_id}

# Create user
POST /api/admin/users
{
  "username": "new.user@example.com",
  "email": "new.user@example.com",
  "full_name": "New User",
  "roles": ["auditor_level_1"]
}

# Update user
PATCH /api/admin/users/{user_id}

# Delete user
DELETE /api/admin/users/{user_id}
```
**Requires:** `manage_users` permission

### Configuration Management
```bash
# Get config
GET /api/admin/config

# Update config
PATCH /api/admin/config
{
  "validation_strictness": "lenient",
  "cache_ttl_seconds": 7200
}
```
**Requires:** `manage_config` permission

### Audit Logs
```bash
# List logs
GET /api/admin/audit-logs?limit=100&action=approve_case

# Export logs
GET /api/admin/audit-logs/export?format=json
GET /api/admin/audit-logs/export?format=csv
```
**Requires:** `view_audit_trail` permission

### Explanation Management
```bash
# List all explanations
GET /api/admin/explanations?limit=50&min_confidence=0.8&is_fallback=false

# Get explanation detail
GET /api/admin/explanations/{explanation_id}

# Delete explanation
DELETE /api/admin/explanations/{explanation_id}

# Force regenerate
POST /api/admin/explanations/{explanation_id}/regenerate
```
**Requires:** `view_admin` permission (delete/regenerate require admin)

### Validation Statistics
```bash
GET /api/admin/validation/stats
GET /api/admin/validation/errors?limit=100&error_type=MISSING_CITATION
```
**Requires:** `view_admin` permission

### Cache Management
```bash
# Get stats
GET /api/admin/cache/stats

# Clear cache
DELETE /api/admin/cache?case_id=CASE-001
DELETE /api/admin/cache?pattern=explanation:case_high_*

# List keys
GET /api/admin/cache/keys?limit=100&prefix=explanation:
```
**Requires:** Admin role

### LLM Provider Management
```bash
# Get providers
GET /api/admin/llm/providers

# Test provider
POST /api/admin/llm/providers/groq/test
POST /api/admin/llm/providers/openai/test

# Switch provider
POST /api/admin/llm/providers/groq/switch
```
**Requires:** Admin role

### Batch Operations
```bash
# Batch regenerate
POST /api/admin/batch/regenerate
{
  "case_ids": ["CASE-001", "CASE-002"],
  "force": false
}

# Batch validate
POST /api/admin/batch/validate
{
  "case_ids": ["CASE-001", "CASE-002"]
}

# Batch clear cache
POST /api/admin/batch/clear-cache
{
  "case_ids": ["CASE-001", "CASE-002"]
}
```
**Requires:** Admin role

### System Operations
```bash
# Reload config
POST /api/admin/system/reload-config

# Get metrics
GET /api/admin/system/metrics

# Warm cache
POST /api/admin/system/cache/warm

# Get settings
GET /api/admin/system/settings

# Update settings
PATCH /api/admin/system/settings
{
  "maintenance_mode": false,
  "auto_regeneration": true
}
```
**Requires:** Admin role

---

## Error Responses

All errors follow this structure:
```json
{
  "detail": "Error message description",
  "status_code": 400
}
```

Common status codes:
- `400` - Bad request (validation failed)
- `401` - Authentication required
- `403` - Insufficient permissions
- `404` - Resource not found
- `422` - Validation error (Pydantic)
- `429` - Rate limit exceeded
- `500` - Internal server error
- `503` - Service unavailable

---

## Rate Limiting
- Default: 200 requests per minute per client
- Configurable via RATE_LIMIT_MAX_REQUESTS and RATE_LIMIT_WINDOW_SECONDS

## Caching
- Explanation results are cached in Redis (or in-memory fallback)
- Default TTL: 3600 seconds (1 hour)
- Cache can be cleared via admin endpoints

## Fallback Behavior
When the primary LLM provider (Groq) is unavailable:
1. Automatic fallback to OpenAI
2. If both fail, template-based fallback explanations are generated
3. Fallback explanations are marked with `is_fallback: true`
