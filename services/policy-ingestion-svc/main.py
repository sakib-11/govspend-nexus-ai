from fastapi import FastAPI
import uvicorn
import asyncpg
from contextlib import asynccontextmanager
from config import PolicyIngestionConfig, get_config
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService
from services.vector_store import VectorStore
from services.ingestion_service import IngestionService
from routes import ingestion as ingestion_routes

config = get_config()
app = FastAPI(
    title="Policy Ingestion Service",
    version="1.0.0",
    description="GovSpend Nexus AI - Policy Document Ingestion with RAG"
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
    
    # Initialize services
    chunking_service = ChunkingService(config)
    embedding_service = EmbeddingService(config)
    vector_store = VectorStore(db_pool, config)
    ingestion_service = IngestionService(
        db_pool=db_pool,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        vector_store=vector_store,
        config=config
    )
    
    # Store in app state
    app.state.db_pool = db_pool
    app.state.chunking_service = chunking_service
    app.state.embedding_service = embedding_service
    app.state.vector_store = vector_store
    app.state.ingestion_service = ingestion_service
    
    yield
    
    # Cleanup
    await db_pool.close()

app.router.lifespan_context = lifespan

# Include routes
app.include_router(ingestion_routes.router)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": config.service_name,
        "version": "1.0.0",
        "embedding_model": config.embedding_model
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.port,
        reload=config.debug
    )
