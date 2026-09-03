"""MCP Gateway — Authentication & RBAC for GovSpend Nexus AI."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_config
from .auth.mfa_handler import MFAHandler
from .auth.session_manager import SessionManager
from .auth.token_validator import TokenValidator
from .auth.user_store import UserStore
from .middleware.auth_middleware import AuthMiddleware
from .middleware.audit_middleware import AuditMiddleware
from .middleware.authorization_middleware import AuthorizationMiddleware
from .rbac.policy_engine import PolicyEngine
from .routes import auth as auth_routes
from .routes import admin as admin_routes
from .routes import authorization as authorization_routes
from .utils.logging import get_logger, setup_logging

config = get_config()
setup_logging(log_level=config.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialise services, yield, cleanup."""

    logger.info("Starting %s service...", config.SERVICE_NAME)

    # ------------------------------------------------------------------
    # Services (all work without external DB/Redis)
    # ------------------------------------------------------------------
    user_store = UserStore(config=config)
    token_validator = TokenValidator(config=config)
    session_manager = SessionManager(config=config)
    mfa_handler = MFAHandler(config=config)
    policy_engine = PolicyEngine()
    auth_engine = AuthorizationEngine(
        db_pool=None,  # Will be set up if using external DB
        redis_client=None,  # Will be set up if using external Redis
        config=config
    )

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------
    audit_middleware = AuditMiddleware()  # in-memory audit store
    auth_middleware = AuthMiddleware(token_validator)
    auth_middleware._user_store = user_store._users  # share in-memory store
    authorization_middleware = AuthorizationMiddleware(auth_engine)

    # ------------------------------------------------------------------
    # Attach to app.state so routes can access services
    # ------------------------------------------------------------------
    app.state.user_store = user_store
    app.state.token_validator = token_validator
    app.state.session_manager = session_manager
    app.state.mfa_handler = mfa_handler
    app.state.policy_engine = policy_engine
    app.state.auth_engine = auth_engine
    app.state.audit_middleware = audit_middleware
    app.state.auth_middleware = auth_middleware
    app.state.authorization_middleware = authorization_middleware

    # Register ASGI middleware (order matters: outermost runs first)
    logger.info("MCP Gateway ready — %s", config.SERVICE_NAME)
    yield

    logger.info("Shutting down %s", config.SERVICE_NAME)


# ------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------
app = FastAPI(
    title="GovSpend Nexus AI — MCP Gateway",
    version="1.0.0",
    description="Authentication & RBAC gateway for the GovSpend detection pipeline",
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


# We add the middleware classes after app creation so they wrap every request.
# NOTE: middleware added via add_middleware is applied in reverse order of
# registration — the *last* add_middleware call becomes the outermost layer.
# We want AuthMiddleware to run first (outermost), then AuthorizationMiddleware, then AuditMiddleware (innermost).
# So we add Audit first, then Authorization, then Auth (Auth is outermost → runs first).

@app.on_event("startup")
async def _add_middleware():
    """Add auth + audit + authorization middleware on startup (app.state is available then)."""
    # These are thin wrappers; the real heavy lifting is in the middleware classes.
    app.add_middleware(AuditMiddleware)
    app.add_middleware(AuthorizationMiddleware, auth_engine=app.state.auth_engine)
    app.add_middleware(AuthMiddleware, token_validator=app.state.token_validator)


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(authorization_routes.router)


@app.get("/")
async def root():
    return {
        "service": config.SERVICE_NAME,
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
