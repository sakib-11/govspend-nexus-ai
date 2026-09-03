import redis.asyncio as redis
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from typing import List, Optional
from datetime import datetime, timedelta
from models.events import (
    RiskEvent, 
    PriorityLevel, 
    PriorityQueueItem,
    EventType
)
from services.event_publisher import EventPublisher
from services.priority_queue_manager import PriorityQueueManager
from services.alert_manager import AlertManager

router = APIRouter(prefix="/api/v1/events", tags=["risk-events"])

def get_redis_client(request: Request):
    return request.app.state.redis

def get_event_publisher(request: Request):
    return request.app.state.event_publisher

def get_priority_manager(request: Request):
    return request.app.state.priority_manager

def get_alert_manager(request: Request):
    return request.app.state.alert_manager

@router.get("/{event_id}", response_model=RiskEvent)
async def get_event(
    event_id: str,
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Get event by ID"""
    
    event_key = f"event:{event_id}"
    data = await redis_client.get(event_key)
    
    if not data:
        raise HTTPException(status_code=404, detail="Event not found")
    
    import json
    event_data = json.loads(data)
    return RiskEvent(**event_data)

@router.get("/transaction/{transaction_id}")
async def get_transaction_events(
    transaction_id: str,
    redis_client: redis.Redis = Depends(get_redis_client),
    limit: int = 100
):
    """Get all events for a transaction"""
    
    events_key = f"transaction:{transaction_id}:events"
    event_ids = await redis_client.smembers(events_key)
    
    if not event_ids:
        return {"events": []}
    
    # Get event data
    events = []
    for event_id in list(event_ids)[:limit]:
        event_key = f"event:{event_id}"
        data = await redis_client.get(event_key)
        if data:
            import json
            events.append(json.loads(data))
    
    return {
        "transaction_id": transaction_id,
        "count": len(events),
        "events": events
    }

@router.post("/publish")
async def publish_event(
    event_data: dict,
    event_publisher: EventPublisher = Depends(get_event_publisher)
):
    """Manually publish a risk event"""
    
    # This would be used for testing or manual triggers
    event = await event_publisher.publish_risk_event(event_data)
    return {"status": "published", "event_id": event.event_id}

@router.get("/priority/queue")
async def get_priority_queue(
    priority_manager: PriorityQueueManager = Depends(get_priority_manager)
):
    """Get status of priority queues"""
    
    sizes = await priority_manager.get_queue_size()
    items = await priority_manager.get_all_items()
    
    return {
        "queue_sizes": sizes,
        "total_items": len(items),
        "items_by_priority": {
            priority: len([i for i in items if i.priority.value == priority])
            for priority in [p.value for p in PriorityLevel]
        }
    }

@router.get("/priority/queue/{priority}")
async def dequeue_priority_item(
    priority: PriorityLevel,
    priority_manager: PriorityQueueManager = Depends(get_priority_manager)
):
    """Dequeue item from priority queue"""
    
    item = await priority_manager.dequeue(priority)
    
    if not item:
        raise HTTPException(status_code=404, detail="No items in queue")
    
    return item

@router.post("/priority/move/{event_id}")
async def move_event_priority(
    event_id: str,
    new_priority: PriorityLevel,
    priority_manager: PriorityQueueManager = Depends(get_priority_manager)
):
    """Move event to different priority queue"""
    
    success = await priority_manager.move_to_priority(event_id, new_priority)
    
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return {"status": "moved", "event_id": event_id, "new_priority": new_priority}

@router.get("/stats")
async def get_event_stats(
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Get event statistics"""
    
    # Count recent events
    now = datetime.now()
    recent_cutoff = (now - timedelta(hours=24)).timestamp()
    
    # Get all event keys
    keys = await redis_client.keys("event:*")
    total_events = len(keys)
    
    # Count recent
    recent_events = 0
    high_risk = 0
    
    for key in keys:
        data = await redis_client.get(key)
        if data:
            import json
            event = json.loads(data)
            
            # Check if recent
            occurred_at = datetime.fromisoformat(event['occurred_at'])
            if (now - occurred_at).total_seconds() < 86400:
                recent_events += 1
            
            if event.get('risk_tier') == 'HIGH':
                high_risk += 1
    
    return {
        "total_events": total_events,
        "events_last_24h": recent_events,
        "high_risk_events": high_risk,
        "timestamp": now.isoformat()
    }

@router.post("/alert/test/{event_id}")
async def test_alert(
    event_id: str,
    alert_manager: AlertManager = Depends(get_alert_manager),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Test alert system with an event"""
    
    event_key = f"event:{event_id}"
    data = await redis_client.get(event_key)
    
    if not data:
        raise HTTPException(status_code=404, detail="Event not found")
    
    import json
    event_data = json.loads(data)
    event = RiskEvent(**event_data)
    
    alerts = await alert_manager.process_event(event)
    sent_alerts = await alert_manager.send_alerts(alerts)
    
    return {
        "alerts_generated": len(alerts),
        "alerts_sent": len(sent_alerts),
        "alerts": [alert.model_dump() for alert in sent_alerts]
    }
