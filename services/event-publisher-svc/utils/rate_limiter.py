import asyncio
import time
from typing import Dict
import redis.asyncio as redis
from collections import defaultdict

class RateLimiter:
    """Rate limiter for event processing"""
    
    def __init__(self, redis_client: redis.Redis, config):
        self.redis = redis_client
        self.config = config
        self.local_counter = defaultdict(int)
        self.last_reset = time.time()
        self.reset_interval = 60  # Reset counters every minute
    
    async def is_allowed(self, key: str, limit: int, window: int = 60) -> bool:
        """Check if request is allowed based on rate limit"""
        
        # Use Redis for distributed rate limiting
        current_time = int(time.time())
        window_start = current_time - window
        
        # Clean old entries and count current ones
        pipeline = self.redis.pipeline()
        pipeline.zremrangebyscore(key, 0, window_start)
        pipeline.zcard(key)
        pipeline.zadd(key, {str(current_time): current_time})
        pipeline.expire(key, window)
        
        results = await pipeline.execute()
        current_count = results[1]
        
        return current_count < limit
    
    async def get_current_count(self, key: str, window: int = 60) -> int:
        """Get current count for a key"""
        
        current_time = int(time.time())
        window_start = current_time - window
        
        # Clean old entries and get count
        await self.redis.zremrangebyscore(key, 0, window_start)
        count = await self.redis.zcard(key)
        
        return count