from typing import Optional, Dict, Any
import json
import redis.asyncio as redis
from datetime import timedelta
from models.jurisdiction import JurisdictionEnforcementResult

class JurisdictionCache:
    """Cache jurisdiction enforcement results"""
    
    def __init__(self, redis_client: redis.Redis, config):
        self.redis = redis_client
        self.config = config
        self.default_ttl = 300  # 5 minutes
    
    async def get(self, key: str) -> Optional[JurisdictionEnforcementResult]:
        """Get cached enforcement result"""
        
        data = await self.redis.get(key)
        if data:
            try:
                result_data = json.loads(data)
                return JurisdictionEnforcementResult(**result_data)
            except Exception:
                return None
        return None
    
    async def set(self, key: str, result: JurisdictionEnforcementResult, ttl: Optional[int] = None):
        """Cache enforcement result"""
        
        ttl = ttl or self.default_ttl
        data = json.dumps(result.model_dump(), default=str)
        await self.redis.setex(key, ttl, data)
    
    async def invalidate(self, key: str):
        """Invalidate cached result"""
        await self.redis.delete(key)
    
    async def invalidate_for_user(self, user_id: str):
        """Invalidate all cached results for a user"""
        pattern = f"jurisdiction:enforcement:*{user_id}*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
    
    async def invalidate_for_resource(self, resource_id: str):
        """Invalidate all cached results for a resource"""
        pattern = f"jurisdiction:enforcement:*{resource_id}*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        
        keys = await self.redis.keys("jurisdiction:enforcement:*")
        return {
            "total_cached": len(keys),
            "cache_key_prefix": "jurisdiction:enforcement:",
            "ttl_seconds": self.default_ttl
        }