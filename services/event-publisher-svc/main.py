from fastapi import FastAPI
from fastapi import Request
import uvicorn
import asyncpg
import redis.asyncio as redis
from contextlib import asynccontextmanager
from config import EventPublisherConfig, get_config
from services.priority_queue_manager import PriorityQueueManager
from services.alert_manager import AlertManager
from services.event_publisher import EventPublisher
from consumers.bundle_consumer import BundleConsumer

# Import integrations
from integrations.slack_notifier import SlackNotifier
from integrations.email_notifier import EmailNotifier
from integrations.webhook_dispatcher import WebhookDispatcher

config = get_config()
app = FastAPI(
    title="Event Publisher Service",
    version="1.0.0",
    description="GovSpend Nexus AI - Risk Event Publishing"
)

# Global instances
db_pool = None
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global db_pool, redis_client
    
    # Initialize database
    db_pool = await asyncpg.create_pool(
        host=config.db_host,
        port=config.db_port,
        database=config.db_name,
        user=config.db_user,
        password=config.db_password,
        min_size=2,
        max_size=10
    )
    
    # Initialize Redis
    redis_client = await redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        decode_responses=True
    )
    
    # Initialize notification clients
    slack_notifier = None
    if config.slack_enabled and config.slack_webhook_url:
        slack_notifier = SlackNotifier(config.slack_webhook_url, config)
    
    email_notifier = None
    if config.email_enabled and config.email_smtp_host:
        email_notifier = EmailNotifier(config)
    
    webhook_dispatcher = None
    if config.webhook_enabled and config.webhook_endpoints:
        webhook_dispatcher = WebhookDispatcher(config)
    
    # Initialize services
    priority_manager = PriorityQueueManager(redis_client, config)
    
    alert_manager = AlertManager(
        redis_client,
        config,
        slack_notifier,
        email_notifier,
        webhook_dispatcher
    )
    
    event_publisher = EventPublisher(
        redis_client,
        priority_manager,
        alert_manager,
        config
    )
    
    # Store in app state
    app.state.db_pool = db_pool
    app.state.redis = redis_client
    app.state.event_publisher = event_publisher
    app.state.priority_manager = priority_manager
    app.state.alert_manager = alert_manager
    
    # Start background consumer
    consumer = BundleConsumer(
        redis_client,
        event_publisher,
        config
    )
    import asyncio
    asyncio.create_task(consumer.consume_loop())
    
    yield
    
    # Cleanup
    await db_pool.close()
    await redis_client.close()

app.router.lifespan_context = lifespan

# Include routes
from routes import events as events_routes
app.include_router(events_routes.router)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": config.service_name,
        "version": "1.0.0"
    }

@app.get("/stats/queue")
async def queue_stats(request: Request):
    """Get queue statistics"""
    priority_manager = request.app.state.priority_manager
    sizes = await priority_manager.get_queue_size()
    return {
        "queue_sizes": sizes,
        "total": sum(sizes.values())
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.port,
        reload=config.debug
    )