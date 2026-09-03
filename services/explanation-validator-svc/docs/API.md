# Explanation Validator Service API Documentation

## Base URL
```
http://localhost:8018
```

## Authentication
All endpoints require authentication via JWT token or session cookie.

### Login
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "auditor@example.com",
  "password": "auditor123"
}
```

---

## Validation Routes

### Validate Explanation
```bash
POST /api/v1/validator/validate
Authorization: Bearer <token>
Content-Type: application/json

{
  "explanation_id": "exp-123",
  "case_id": "case-456",
  "content": {
    "summary": "Valid explanation with sufficient length",
    "explanations": [
      {
        "point_number": 1,
        "detector_name": "price_deviation",
        "sentence": "Valid explanation sentence with enough characters",
        "confidence": 0.9,
        "evidence_ids": ["EV-001"],
        "policy_references": ["GFR-4.3"]
      }
    ]
  },
  "evidence_bundle": {
    "evidence": [
      {"id": "EV-001", "type": "invoice", "description": "Invoice price 50% above market"}
    ]
  },
  "retrieved_policies": [
    {"policy_id": "GFR-4.3", "title": "Procurement Rules", "content": "Procurement at market rates"}
  ],
  "signals": [
    {"detector_type": "price_deviation", "signal_value": 0.9, "confidence": 0.95, "evidence_ids": ["EV-001"]}
  ],
  "strict_mode": true,
  "mask_ungrounded": true,
  "rephrase_ungrounded": true
}
```

**Response:**
```json
{
  "validation_id": "val-abc123",
  "explanation_id": "exp-123",
  "case_id": "case-456",
  "status": "passed",
  "grounding_score": 1.0,
  "citation_coverage": 1.0,
  "schema_valid": true,
  "citations_valid": true,
  "evidence_valid": true,
  "policy_valid": true,
  "detector_names_valid": true,
  "grounding_checks": [...],
  "citation_validations": [...],
  "errors": [],
  "warnings": [],
  "validation_time_ms": 45.2
}
```

### Get Validation Result
```bash
GET /api/v1/validator/result/{validation_id}
Authorization: Bearer <token>
```

### Get Validation Stats
```bash
GET /api/v1/validator/stats
Authorization: Bearer <token>
```
**Requires:** Admin role

---

## Validation Status Values

- `passed` - All validations passed
- `failed` - Validation failed
- `partial` - Partial validation (some issues found)
- `grounded` - Grounding check passed
- `ungrounded` - Grounding check failed
- `masked` - Ungrounded claims were masked

## Citation Status Values

- `valid` - Citation is valid and exists in corpus
- `invalid` - Citation reference not found
- `partial` - Partial match found
- `missing` - Citation is missing

## Error Responses

```json
{
  "error": {
    "error_id": "uuid",
    "error_code": "VALIDATION_ERROR",
    "message": "Error description",
    "severity": "high",
    "timestamp": "2024-01-01T00:00:00Z",
    "details": {}
  },
  "meta": {
    "request_id": "uuid",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```
