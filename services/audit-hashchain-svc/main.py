from fastapi import FastAPI
import uvicorn
import asyncpg
import redis.asyncio as redis
from contextlib import asynccontextmanager
from config import HashChainConfig, get_config
from services.hashchain_service import HashChainService
from services.notary_publisher import NotaryPublisher
from services.blockchain_publisher import BlockchainPublisher
from services.snapshot_service import SnapshotService
from consumers.audit_consumer import AuditConsumer
from routes import hashchain as hashchain_routes
from routes import verification as verification_routes

config = get_config()
app = FastAPI(
    title="Audit Hash-Chain Service",
    version="1.0.0",
    description="GovSpend Nexus AI - Tamper-Evident Hash Chain Service"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    
    # Initialize database
    db_pool = await asyncpg.create_pool(
        host=config.db_host,
        port=config.db_port,
        database=config.db_name,
        user=config.db_user,
        password=config.db_password,
        min_size=5,
        max_size=20
    )
    
    # Initialize Redis
    redis_client = await redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        decode_responses=True
    )
    
    # Initialize services
    hashchain_service = HashChainService(db_pool, config)
    notary_publisher = NotaryPublisher(config)
    blockchain_publisher = BlockchainPublisher(config)
    snapshot_service = SnapshotService(
        hashchain_service=hashchain_service,
        notary_publisher=notary_publisher,
        blockchain_publisher=blockchain_publisher,
        config=config
    )
    audit_consumer = AuditConsumer(
        redis_client=redis_client,
        hashchain_service=hashchain_service,
        config=config
    )
    
    # Start background services
    await audit_consumer.start()
    await snapshot_service.start()
    
    # Store in app state
    app.state.db_pool = db_pool
    app.state.redis = redis_client
    app.state.hashchain_service = hashchain_service
    app.state.notary_publisher = notary_publisher
    app.state.blockchain_publisher = blockchain_publisher
    app.state.snapshot_service = snapshot_service
    app.state.audit_consumer = audit_consumer
    
    yield
    
    # Cleanup
    await audit_consumer.stop()
    await snapshot_service.stop()
    await db_pool.close()
    await redis_client.close()
    await notary_publisher.close()

app.router.lifespan_context = lifespan

# Include routes
app.include_router(hashchain_routes.router)
app.include_router(verification_routes.router)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": config.service_name,
        "version": "1.0.0",
        "notary_enabled": config.notary_enabled,
        "blockchain_enabled": config.blockchain_enabled
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.port,
        reload=config.debug
    )
