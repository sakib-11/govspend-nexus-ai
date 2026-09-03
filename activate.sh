#!/bin/bash
# Activate GovSpend Nexus AI development environment

echo "🚀 Activating GovSpend Nexus AI Environment..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Installing..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

# Activate Poetry environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  Virtual environment not found. Running poetry install..."
    poetry install --no-root
    source .venv/bin/activate
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Environment variables loaded"
else
    echo "⚠️  .env file not found. Creating from example..."
    cp .env.example .env
    echo "✅ .env created. Please update with your values."
fi

# Check Docker
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null; then
        echo "✅ Docker running"
    else
        echo "⚠️  Docker not running. Starting..."
        sudo systemctl start docker
    fi
else
    echo "⚠️  Docker not found. Please install Docker."
fi

echo ""
echo "📋 GovSpend Nexus AI Environment Ready!"
echo ""
echo "Commands:"
echo "  poetry shell          - Enter virtual environment"
echo "  poetry run pytest     - Run tests"
echo "  docker compose up -d  - Start infrastructure"
echo "  python run_services.py - Start all services"
echo ""

# Enter Poetry shell
exec poetry shell
