"""Jurisdiction Enforcement Service"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_config
from .services.hierarchy_manager import HierarchyManager
from .services.jurisdiction_enforcer import JurisdictionEnforcer
from .services.jurisdiction_cache import JurisdictionCache
from .services.enforcement_audit import EnforcementAudit
from .middleware.jurisdiction_middleware import JurisdictionMiddleware
from .routes import jurisdiction as jurisdiction_routes
from .utils.logging import get_logger, setup_logging

config = get_config()
setup_logging(log_level=config.LOG_LEVEL)
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialise services, yield, cleanup."""
    
    logger.info("Starting %s service...", config.SERVICE_NAME)
    
    # Initialize database connection pool (mock for now)
    # In production, you'd use asyncpg.create_pool or similar
    db_pool = None  # Mock
    redis_client = None  # Mock
    
    # Initialize services
    hierarchy_manager = HierarchyManager(db_pool)
    jurisdiction_cache = JurisdictionCache(redis_client, config)
    enforcement_audit = EnforcementAudit(db_pool)
    jurisdiction_enforcer = JurisdictionEnforcer(
        hierarchy_manager, 
        jurisdiction_cache, 
        enforcement_audit
    )
    
    # Initialize middleware
    jurisdiction_middleware = JurisdictionMiddleware(jurisdiction_enforcer)
    
    # Attach to app.state so routes can access services
    app.state.hierarchy_manager = hierarchy_manager
    app.state.jurisdiction_cache = jurisdiction_cache
    app.state.enforcement_audit = enforcement_audit
    app.state.jurisdiction_enforcer = jurisdiction_enforcer
    app.state.jurisdiction_middleware = jurisdiction_middleware
    
    logger.info("%s service ready", config.SERVICE_NAME)
    yield
    
    logger.info("Shutting down %s", config.SERVICE_NAME)

# FastAPI app
app = FastAPI(
    title="Jurisdiction Enforcement Service",
    version="1.0.0",
    description="Service for enforcing jurisdiction-based access control",
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

# Add jurisdiction enforcement middleware
app.add_middleware(JurisdictionMiddleware, enforcer=app.state.jurisdiction_enforcer)

# Include routes
app.include_router(jurisdiction_routes.router)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "service": config.SERVICE_NAME,
        "status": "running",
        "version": "1.0.0",
    }