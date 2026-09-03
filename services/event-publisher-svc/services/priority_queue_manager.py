import json
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import redis.asyncio as redis
from models.events import PriorityLevel, PriorityQueueItem, RiskEvent

class PriorityQueueManager:
    """Manage priority queues for risk events"""
    
    def __init__(self, redis_client: redis.Redis, config):
        self.redis = redis_client
        self.config = config
        
        # Queue mappings by priority
        self.queue_map = {
            PriorityLevel.CRITICAL: self.config.critical_queue,
            PriorityLevel.HIGH: self.config.high_queue,
            PriorityLevel.MEDIUM: self.config.medium_queue,
            PriorityLevel.LOW: self.config.low_queue,
            PriorityLevel.BACKGROUND: "background_queue"
        }
        
        # Queue priorities (lower number = higher priority)
        self.priority_order = [
            PriorityLevel.CRITICAL,
            PriorityLevel.HIGH,
            PriorityLevel.MEDIUM,
            PriorityLevel.LOW,
            PriorityLevel.BACKGROUND
        ]
    
    async def enqueue(
        self, 
        event: RiskEvent, 
        payload: Dict[str, Any]
    ) -> bool:
        """Enqueue event to appropriate priority queue"""
        
        queue_name = self.queue_map.get(event.priority)
        if not queue_name:
            return False
        
        item = PriorityQueueItem(
            event_id=event.event_id,
            transaction_id=event.transaction_id,
            priority=event.priority,
            payload=payload
        )
        
        # Store in queue with score (timestamp for ordering)
        score = datetime.now().timestamp()
        item_json = json.dumps(item.model_dump(), default=str)
        
        await self.redis.zadd(queue_name, {item_json: score})
        
        # Also store in main queue for tracking
        await self.redis.zadd(
            self.config.priority_queue_key,
            {item_json: score}
        )
        
        return True
    
    async def dequeue(
        self, 
        priority: Optional[PriorityLevel] = None
    ) -> Optional[PriorityQueueItem]:
        """Dequeue the highest priority item"""
        
        if priority:
            queues = [self.queue_map.get(priority)]
        else:
            # Get from all queues in priority order
            queues = [
                self.queue_map.get(p) 
                for p in self.priority_order 
                if self.queue_map.get(p)
            ]
        
        for queue_name in queues:
            if not queue_name:
                continue
            
            # Get oldest item (smallest score)
            items = await self.redis.zrange(
                queue_name, 
                0, 0, 
                withscores=True
            )
            
            if items:
                item_data = items[0][0]  # First item
                item = PriorityQueueItem(**json.loads(item_data))
                
                # Remove from queue
                await self.redis.zrem(queue_name, item_data)
                await self.redis.zrem(
                    self.config.priority_queue_key, 
                    item_data
                )
                
                return item
        
        return None
    
    async def get_queue_size(self) -> Dict[str, int]:
        """Get size of each priority queue"""
        
        sizes = {}
        for priority, queue_name in self.queue_map.items():
            size = await self.redis.zcard(queue_name)
            sizes[priority.value] = size
        
        return sizes
    
    async def get_all_items(self) -> List[PriorityQueueItem]:
        """Get all items from all queues"""
        
        all_items = []
        
        for queue_name in self.queue_map.values():
            items = await self.redis.zrange(
                queue_name, 
                0, -1
            )
            
            for item_data in items:
                try:
                    item = PriorityQueueItem(**json.loads(item_data))
                    all_items.append(item)
                except Exception:
                    continue
        
        # Sort by priority
        priority_map = {p.value: idx for idx, p in enumerate(self.priority_order)}
        all_items.sort(key=lambda x: priority_map.get(x.priority.value, 999))
        
        return all_items
    
    async def update_item(
        self, 
        event_id: str, 
        update_fn
    ) -> bool:
        """Update an item in the queue"""
        
        # Find and update item
        for queue_name in self.queue_map.values():
            items = await self.redis.zrange(queue_name, 0, -1)
            
            for item_data in items:
                try:
                    item = PriorityQueueItem(**json.loads(item_data))
                    if item.event_id == event_id:
                        # Apply update
                        update_fn(item)
                        
                        # Replace item
                        new_data = json.dumps(item.model_dump(), default=str)
                        score = datetime.now().timestamp()
                        
                        await self.redis.zrem(queue_name, item_data)
                        await self.redis.zadd(queue_name, {new_data: score})
                        
                        return True
                except Exception:
                    continue
        
        return False
    
    async def cleanup_expired(self, max_age_hours: int = 48) -> int:
        """Clean up expired items from queues"""
        
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        cutoff_score = cutoff.timestamp()
        
        removed_count = 0
        
        for queue_name in self.queue_map.values():
            # Remove items older than cutoff
            removed = await self.redis.zremrangebyscore(
                queue_name, 
                '-inf', 
                cutoff_score
            )
            removed_count += removed
        
        return removed_count
    
    async def move_to_priority(
        self, 
        event_id: str, 
        new_priority: PriorityLevel
    ) -> bool:
        """Move an event to a different priority queue"""
        
        # Find and move item
        for queue_name in self.queue_map.values():
            items = await self.redis.zrange(queue_name, 0, -1)
            
            for item_data in items:
                try:
                    item = PriorityQueueItem(**json.loads(item_data))
                    if item.event_id == event_id:
                        # Remove from current queue
                        await self.redis.zrem(queue_name, item_data)
                        
                        # Update priority
                        item.priority = new_priority
                        
                        # Add to new queue
                        new_queue = self.queue_map.get(new_priority)
                        if new_queue:
                            new_data = json.dumps(item.model_dump(), default=str)
                            score = datetime.now().timestamp()
                            await self.redis.zadd(new_queue, {new_data: score})
                            return True
                        
                except Exception:
                    continue
        
        return False