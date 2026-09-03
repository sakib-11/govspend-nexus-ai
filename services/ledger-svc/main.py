from fastapi import FastAPI
import uvicorn
import asyncpg
import ssl
from contextlib import asynccontextmanager
from config import LedgerConfig, get_config
from services.hsm_client import HSMClient
from services.encryption_service import EncryptionService
from services.ledger_service import LedgerService
from middleware.auth_middleware import AuthMiddleware
from routes import ledger as ledger_routes

config = get_config()
app = FastAPI(
    title="Ledger Service",
    version="1.0.0",
    description="GovSpend Nexus AI - Secure Ledger Service"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    
    # Configure SSL for database connection
    ssl_context = None
    if config.db_ssl_mode == "require":
        ssl_context = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH,
            cafile=config.tls_ca_path if config.tls_ca_path else None
        )
    
    # Initialize database
    db_pool = await asyncpg.create_pool(
        host=config.db_host,
        port=config.db_port,
        database=config.db_name,
        user=config.db_user,
        password=config.db_password,
        ssl=ssl_context,
        min_size=config.db_pool_min,
        max_size=config.db_pool_max,
        command_timeout=10
    )
    
    # Initialize HSM
    hsm_client = HSMClient(config)
    encryption_service = EncryptionService(hsm_client)
    ledger_service = LedgerService(db_pool, encryption_service, hsm_client, config)
    
    # Store in app state
    app.state.db_pool = db_pool
    app.state.hsm_client = hsm_client
    app.state.encryption_service = encryption_service
    app.state.ledger_service = ledger_service
    
    yield
    
    # Cleanup
    await db_pool.close()

app.router.lifespan_context = lifespan

# Add auth middleware
app.add_middleware(AuthMiddleware, config=config)

# Include routes
app.include_router(ledger_routes.router)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": config.service_name,
        "version": "1.0.0",
        "hsm_enabled": config.hsm_enabled
    }

@app.get("/api/v1/status")
async def status():
    return {
        "service": "ledger-svc",
        "status": "operational",
        "encryption_algorithm": config.encryption_algorithm,
        "hsm_enabled": config.hsm_enabled,
        "db_connected": True
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.port,
        reload=config.debug,
        ssl_keyfile=config.tls_key_path if config.tls_enabled else None,
        ssl_certfile=config.tls_cert_path if config.tls_enabled else None,
        ssl_ca_certs=config.tls_ca_path if config.tls_enabled else None
    )
