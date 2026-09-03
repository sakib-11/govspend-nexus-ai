# 🤝 Contributing to GovSpend Nexus AI

Thank you for your interest in contributing to GovSpend Nexus AI! This document provides guidelines and information for contributors.

## 📋 Table of Contents

- [Getting Started](#-getting-started)
- [Development Setup](#-development-setup)
- [Code Style](#-code-style)
- [Testing](#-testing)
- [Pull Request Process](#-pull-request-process)
- [Code of Conduct](#-code-of-conduct)

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Poetry (Python package manager)
- Git

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/govspend-nexus-ai.git
   cd govspend-nexus-ai
   ```

3. Add the upstream remote:
   ```bash
   git remote add upstream https://github.com/your-org/govspend-nexus-ai.git
   ```

## 🛠️ Development Setup

### Backend Setup

```bash
# Install Poetry if not installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Copy environment variables
cp .env.example .env

# Start development server
poetry run uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd govspend-frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Docker Setup

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f
```

## 📝 Code Style

### Python

- Follow PEP 8 guidelines
- Use Black for code formatting
- Use Ruff for linting
- Maximum line length: 100 characters

```bash
# Format code
poetry run black .

# Lint code
poetry run ruff check .
```

### TypeScript/React

- Follow Airbnb style guide
- Use ESLint and Prettier
- Use functional components with hooks

```bash
# Lint frontend code
cd govspend-frontend
npm run lint

# Format frontend code
npm run format
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=services --cov-report=html

# Run specific test types
poetry run pytest tests/unit/
poetry run pytest tests/integration/
poetry run pytest tests/security/

# Frontend tests
cd govspend-frontend
npm test
```

### Writing Tests

- Write tests for new features
- Maintain or improve test coverage
- Use descriptive test names
- Follow the Arrange-Act-Assert pattern

## 📬 Pull Request Process

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Make your changes:**
   - Write clean, documented code
   - Add tests for new functionality
   - Update documentation if needed

3. **Commit your changes:**
   ```bash
   git commit -m "feat: Add amazing feature"
   ```

   Use [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `test:` for tests
   - `refactor:` for code refactoring

4. **Push to your fork:**
   ```bash
   git push origin feature/amazing-feature
   ```

5. **Create a Pull Request:**
   - Provide a clear title and description
   - Reference any related issues
   - Include screenshots if applicable
   - Ensure CI passes

## 📜 Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive experience for everyone. We pledge to act and interact in ways that contribute to an open, friendly, diverse, and healthy community.

### Standards

Examples of behavior that contributes to a positive environment:

- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community

Examples of unacceptable behavior:

- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without explicit permission
- Other conduct which could reasonably be considered inappropriate

## 🆘 Getting Help

- **Issues:** Create a GitHub issue for bugs or feature requests
- **Discussions:** Use GitHub Discussions for questions and ideas
- **Email:** Contact maintainers at team@auditcore.gov

## 📚 Resources

- [Project Documentation](docs/)
- [API Documentation](http://localhost:8000/docs)
- [Architecture Overview](docs/architecture/)

---

Thank you for contributing to GovSpend Nexus AI! 🛡️
