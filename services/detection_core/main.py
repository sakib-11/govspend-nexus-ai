"""Main entry point for Detection Core Service."""

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .consumers.stream_consumer import StreamConsumer
from .engine.orchestrator import DetectionOrchestrator
from .routes import engine
from .utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Global instances
orchestrator: DetectionOrchestrator = None
consumer: StreamConsumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global orchestrator, consumer

    logger.info(f"Starting {app.title} service...")

    # Initialize orchestrator
    orchestrator = DetectionOrchestrator()

    # Initialize consumer
    async def message_handler(transaction):
        """Handle incoming transaction messages"""
        try:
            logger.info(f"Processing transaction: {transaction.get('transaction_id')}")
            result = await orchestrator.process_transaction(transaction)
            logger.info(f"Transaction processed: {result}")
        except Exception as e:
            logger.error(f"Failed to process transaction: {e}")

    consumer = StreamConsumer(
        redis_url=settings.REDIS_URL,
        consumer_group=settings.CONSUMER_GROUP or "detection_group",
        consumer_name=f"detection_{settings.HOST}_{settings.PORT}",
    )
    consumer.register_handler(settings.INPUT_STREAM or "tx.ingested", message_handler)

    # Start consumer in background
    consumer_task = asyncio.create_task(consumer.start())

    yield

    # Cleanup
    logger.info(f"Shutting down {app.title} service...")
    await consumer.stop()
    await orchestrator.stop()
    consumer_task.cancel()
    with suppress(asyncio.CancelledError):
        await consumer_task

# Initialize FastAPI app
app = FastAPI(
    title="GovSpend Nexus AI - Detection Core",
    version="1.0.0",
    description="Detection engine orchestrating all detectors",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(engine.router, prefix="/api/v1", tags=["Engine"])

@app.get("/")
async def root():
    return {
        "service": "detection-core",
        "status": "running",
        "version": "1.0.0",
        "detectors": orchestrator.registry.get_all_detectors_metadata() if orchestrator else {}
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "detection-core",
        "timestamp": datetime.utcnow().isoformat(),
        "active_transactions": len(orchestrator._active_transactions) if orchestrator else 0
    }