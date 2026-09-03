"""MCP Gateway & Tools API — main application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_config
from tools.registry import ToolRegistry
from services.tool_executor import ToolExecutor
from services.schema_validator import SchemaValidator
from services.audit_service import AuditService
from mcp.server import MCPServer

from routes import mcp as mcp_routes
from routes import tools as tools_routes
from routes import schemas as schemas_routes

config = get_config()

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialise services, yield, cleanup."""

    logger.info("Starting %s service on port %d", config.SERVICE_NAME, config.PORT)

    # Build the MCP server (initialises registry + handlers)
    server = MCPServer()
    server.initialise()

    audit_service = AuditService(max_entries=config.AUDIT_MAX_ENTRIES)
    schema_validator = SchemaValidator()
    tool_executor = ToolExecutor(server.registry, schema_validator)

    # Attach to app.state for route access
    app.state.tool_registry = server.registry
    app.state.tool_executor = tool_executor
    app.state.audit_service = audit_service
    app.state.schema_validator = schema_validator
    app.state.mcp_server = server

    logger.info(
        "%s ready — %d tools registered",
        config.SERVICE_NAME,
        len(server.registry.get_all_tools()),
    )

    yield

    logger.info("Shutting down %s", config.SERVICE_NAME)


# ------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------

app = FastAPI(
    title="MCP Gateway & Tools API",
    version="1.0.0",
    description=(
        "GovSpend Nexus AI — secure MCP Gateway exposing schema-validated "
        "tools for approved government audit actions."
    ),
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

app.include_router(mcp_routes.router)
app.include_router(tools_routes.router)
app.include_router(schemas_routes.router)


@app.get("/")
async def root():
    return {
        "service": config.SERVICE_NAME,
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    registry = getattr(app.state, "tool_registry", None)
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tools_registered": len(registry.get_all_tools()) if registry else 0,
    }


@app.get("/api/v1/mcp/status")
async def mcp_status():
    """MCP protocol status endpoint."""
    registry = getattr(app.state, "tool_registry", None)
    return {
        "status": "operational",
        "version": "1.0.0",
        "protocol_version": "1.0",
        "tools_registered": len(registry.get_all_tools()) if registry else 0,
    }


# ------------------------------------------------------------------
# Standalone
# ------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
    )
