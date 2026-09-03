# GovSpend Nexus AI

> **Government Spend Audit & Procurement Intelligence System**

An AI-powered microservices platform that detects fraud, anomalies, and irregularities in government procurement and spending.

---

## Features

- **AI-Powered Fraud Detection** — Machine learning algorithms analyze transactions in real-time
- **Real-Time Analytics** — Live dashboards with interactive visualizations
- **Blockchain Audit Trail** — Immutable audit trails for compliance and transparency
- **Multi-Jurisdiction Support** — Handles complex government regulations across regions
- **Enterprise Security** — Role-based access, encryption, and SOC2 compliance
- **Responsive Design** — Mobile-first approach with modern UI components

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, TypeScript, Material UI, Zustand, Recharts |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy, Pydantic |
| **Database** | PostgreSQL 15 + pgvector, Redis 7 |
| **Messaging** | Apache Kafka, Redis Pub/Sub |
| **Infrastructure** | Docker, Kubernetes, Terraform, Helm |
| **CI/CD** | GitHub Actions |

---

## Architecture

```
                        ┌─────────────────────┐
                        │    React Frontend    │
                        │   (TypeScript/MUI)   │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │     MCP Gateway      │
                        │   (Auth / Routing)   │
                        └──────────┬──────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────▼─────────┐  ┌──────────▼──────────┐  ┌─────────▼─────────┐
│   Ingestion Svc   │  │   Detection Core    │  │   Scoring Svc     │
│  (OCR / Parsing)  │  │  (ML Detectors)     │  │  (Risk Scoring)   │
└─────────┬─────────┘  └──────────┬──────────┘  └─────────┬─────────┘
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────▼─────────┐  ┌──────────▼──────────┐  ┌─────────▼─────────┐
│  Explanation Svc  │  │  Evidence Bundle    │  │   Audit Log Svc   │
│  (AI Explanations)│  │  (Evidence Mgmt)    │  │  (Audit Trails)   │
└─────────┬─────────┘  └──────────┬──────────┘  └─────────┬─────────┘
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
              ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
              │ PostgreSQL │ │   Redis   │ │   Kafka   │
              │ (+pgvector)│ │           │ │           │
              └───────────┘ └───────────┘ └───────────┘
```

---

## Project Structure

```
govspend-nexus-ai/
├── govspend-frontend/          # React TypeScript Frontend
│   ├── src/components/         # UI components (admin, auditor, officer)
│   ├── src/pages/              # Route pages
│   ├── src/store/              # Zustand state management
│   ├── src/services/           # API clients
│   └── src/hooks/              # Custom React hooks
│
├── services/                   # Microservices
│   ├── ingestion-svc/          # Document ingestion & OCR
│   ├── detection-svc/          # Fraud detection algorithms
│   ├── detection-core/         # Core detection engine
│   ├── scoring-svc/            # Risk scoring & classification
│   ├── mcp-gateway/            # API gateway & authentication
│   ├── explanation-svc/        # AI-powered explanations
│   ├── evidence_bundle_svc/    # Evidence collection & bundling
│   ├── ledger-svc/             # Immutable audit ledger
│   ├── audit-log-svc/          # Audit logging
│   ├── unmask-svc/             # Data unmasking service
│   ├── digital-twin-svc/       # Transaction simulation
│   ├── policy-weights-svc/     # Policy management
│   └── event-publisher-svc/    # Event publishing & notifications
│
├── libs/                       # Shared libraries
│   ├── crypto/                 # Encryption utilities
│   ├── shared/                 # Common models & config
│   └── schemas/                # JSON schemas
│
├── tests/                      # Test suites
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── e2e/                    # End-to-end tests
│   ├── security/               # Security tests
│   └── load/                   # Performance tests
│
├── infra/                      # Infrastructure
│   ├── docker/                 # Docker configs
│   ├── kubernetes/             # K8s manifests
│   ├── terraform/              # Infrastructure as Code
│   └── helm/                   # Helm charts
│
├── scripts/                    # Automation scripts
├── docs/                       # Documentation
├── docker-compose.yml          # Docker orchestration
├── pyproject.toml              # Python dependencies
└── package.json                # Node.js dependencies
```

---

## Services

| Service | Port | Description |
|---------|------|-------------|
| `ingestion-svc` | 8001 | Document ingestion & OCR processing |
| `detection-svc` | 8002 | Fraud detection algorithms |
| `detection-core` | 8003 | Core detection engine |
| `scoring-svc` | 8004 | Risk scoring & classification |
| `evidence-bundle-svc` | 8005 | Evidence collection & bundling |
| `explanation-svc` | 8006 | AI-powered explanations |
| `digital-twin-svc` | 8007 | Transaction simulation |
| `mcp-gateway` | 8009 | API gateway & authentication |
| `unmask-svc` | 8010 | Data unmasking service |
| `ledger-svc` | 8011 | Immutable audit ledger |
| `audit-log-svc` | 8012 | Audit logging service |
| `policy-weights-svc` | 8013 | Policy management |
| `event-publisher-svc` | 8014 | Event publishing & notifications |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Poetry

### Quick Start

```bash
# Clone the repo
git clone https://github.com/your-org/govspend-nexus-ai.git
cd govspend-nexus-ai

# Copy environment config
cp .env.example .env

# Start all services
docker compose up -d
```

### Development

```bash
# Backend
poetry install
poetry run uvicorn main:app --reload --port 8000

# Frontend
cd govspend-frontend
npm install
npm run dev
```

### Access

- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs
- Admin Panel: http://localhost:8000/admin

---

## Testing

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=services --cov-report=html

# Unit tests
poetry run pytest tests/unit/

# Integration tests
poetry run pytest tests/integration/

# Security tests
poetry run pytest tests/security/

# Frontend tests
cd govspend-frontend
npm test
```

---

## Security

- **Authentication**: Keycloak + OAuth2 + JWT
- **Authorization**: Role-based access control (RBAC)
- **Encryption**: AES-256 at rest, TLS 1.3 in transit
- **MFA**: Multi-factor authentication support
- **Audit**: Immutable blockchain-style audit trails
- **Rate Limiting**: API throttling and protection

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

**Built by AuditCore Innovators for Government Transparency**
