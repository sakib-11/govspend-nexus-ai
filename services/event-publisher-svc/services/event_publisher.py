import json
import asyncio
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import redis.asyncio as redis
from models.events import (
    RiskEvent, 
    EventType, 
    EventSource, 
    PriorityLevel,
    CaseStatus
)
from services.priority_queue_manager import PriorityQueueManager
from services.alert_manager import AlertManager

class EventPublisher:
    """Publish risk events to streams and queues"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        priority_manager: PriorityQueueManager,
        alert_manager: AlertManager,
        config
    ):
        self.redis = redis_client
        self.priority_manager = priority_manager
        self.alert_manager = alert_manager
        self.config = config
        
        # Optional Kafka client
        self.kafka_client = None
        if config.kafka_enabled:
            try:
                from integrations.kafka_client import KafkaClient
                self.kafka_client = KafkaClient(config)
            except ImportError:
                pass
    
    async def publish_risk_event(self, bundle_data: Dict[str, Any]) -> RiskEvent:
        """
        Publish risk event from evidence bundle
        
        Args:
            bundle_data: Evidence bundle data with risk scoring
        """
        
        # Extract data
        transaction_id = bundle_data.get('transaction_id')
        risk_score = bundle_data.get('risk_score', 0.0)
        risk_tier = bundle_data.get('risk_tier', 'LOW')
        weights_version = bundle_data.get('weights_version')
        detectors = bundle_data.get('detectors_used', [])
        
        # Determine priority
        priority = self._determine_priority(risk_score, risk_tier)
        
        # Create event
        event = RiskEvent(
            event_type=EventType.RISK_SCORED,
            source=EventSource.EVIDENCE_BUNDLE_SERVICE,
            source_id=bundle_data.get('bundle_id', transaction_id),
            transaction_id=transaction_id,
            bundle_id=bundle_data.get('bundle_id'),
            risk_score=risk_score,
            risk_tier=risk_tier,
            priority=priority,
            summary=self._generate_summary(risk_score, risk_tier, detectors),
            description=self._generate_description(bundle_data),
            detectors_triggered=detectors,
            metadata=bundle_data.get('metadata', {}),
            tags=self._generate_tags(risk_tier, detectors),
            expires_at=datetime.now() + timedelta(days=7)  # Expire after 7 days
        )
        
        # Create case for non-low risk
        if risk_tier in ['HIGH', 'BORDERLINE']:
            event.case_id = await self._create_case(event)
            event.case_status = CaseStatus.NEW
        
        # Store event
        await self._store_event(event)
        
        # Publish to Redis stream
        await self._publish_to_stream(event)
        
        # Enqueue to priority queue
        await self.priority_manager.enqueue(
            event,
            event.model_dump()
        )
        
        # Process alerts
        alerts = await self.alert_manager.process_event(event)
        if alerts:
            await self.alert_manager.send_alerts(alerts)
        
        # Publish to Kafka (if enabled)
        if self.kafka_client:
            await self._publish_to_kafka(event)
        
        # Publish to Webhooks (if enabled)
        await self._publish_to_webhooks(event)
        
        return event
    
    def _determine_priority(self, risk_score: float, risk_tier: str) -> PriorityLevel:
        """Determine priority based on risk score and tier"""
        
        if risk_tier == "HIGH":
            if risk_score >= 0.90:
                return PriorityLevel.CRITICAL
            elif risk_score >= 0.80:
                return PriorityLevel.HIGH
            else:
                return PriorityLevel.HIGH
        
        elif risk_tier == "BORDERLINE":
            if risk_score >= 0.60:
                return PriorityLevel.MEDIUM
            else:
                return PriorityLevel.LOW
        
        else:  # LOW
            if risk_score >= 0.30:
                return PriorityLevel.LOW
            else:
                return PriorityLevel.BACKGROUND
    
    async def _store_event(self, event: RiskEvent):
        """Store event in database"""
        
        # In production, you'd store in PostgreSQL
        # For now, store in Redis as cache
        event_key = f"event:{event.event_id}"
        await self.redis.set(
            event_key,
            json.dumps(event.model_dump(), default=str),
            ex=86400 * 7  # 7 days
        )
        
        # Add to index
        await self.redis.sadd(f"transaction:{event.transaction_id}:events", event.event_id)
    
    async def _publish_to_stream(self, event: RiskEvent):
        """Publish event to Redis stream"""
        
        await self.redis.xadd(
            self.config.output_stream,
            {
                'event': json.dumps(event.model_dump(), default=str)
            },
            maxlen=10000
        )
    
    async def _publish_to_kafka(self, event: RiskEvent):
        """Publish event to Kafka"""
        
        if not self.kafka_client:
            return
        
        try:
            await self.kafka_client.produce(
                topic=self.config.kafka_topic_risk_events,
                value=json.dumps(event.model_dump(), default=str)
            )
        except Exception as e:
            # Log error but don't fail
            print(f"Kafka publish error: {e}")
    
    async def _publish_to_webhooks(self, event: RiskEvent):
        """Publish event to webhooks"""
        
        if not self.config.webhook_enabled:
            return
        
        for endpoint in self.config.webhook_endpoints:
            try:
                from integrations.webhook_dispatcher import WebhookDispatcher
                dispatcher = WebhookDispatcher(self.config)
                await dispatcher.dispatch(
                    data=event.model_dump(),
                    endpoint=endpoint
                )
            except Exception as e:
                print(f"Webhook error: {e}")
    
    async def _create_case(self, event: RiskEvent) -> str:
        """Create a case for the risk event"""
        
        # In production, you'd create a case in your case management system
        # For now, return a generated case ID
        import uuid
        case_id = f"case-{uuid.uuid4().hex[:12]}"
        
        # Store case in Redis
        case_data = {
            'case_id': case_id,
            'transaction_id': event.transaction_id,
            'risk_score': event.risk_score,
            'risk_tier': event.risk_tier,
            'status': 'NEW',
            'created_at': datetime.now().isoformat(),
            'events': [event.event_id]
        }
        
        await self.redis.set(
            f"case:{case_id}",
            json.dumps(case_data),
            ex=86400 * 30  # 30 days
        )
        
        return case_id
    
    def _generate_summary(self, risk_score: float, risk_tier: str, detectors: List[str]) -> str:
        """Generate event summary"""
        
        tier_text = risk_tier.lower()
        detector_text = ', '.join(detectors[:3])
        if len(detectors) > 3:
            detector_text += f" and {len(detectors) - 3} more"
        
        return f"{risk_score:.1%} risk score ({tier_text} risk) triggered by {detector_text}"
    
    def _generate_description(self, bundle_data: Dict[str, Any]) -> str:
        """Generate detailed description"""
        
        description = f"""
Risk Analysis Summary
---------------------
Risk Score: {bundle_data.get('risk_score', 0.0):.2%}
Risk Tier: {bundle_data.get('risk_tier', 'LOW')}
Confidence: {bundle_data.get('confidence_factor', 0.0):.2%}
Weights Version: {bundle_data.get('weights_version', 'N/A')}

Detectors Triggered:
{chr(10).join(f"• {d}" for d in bundle_data.get('detectors_used', []))}

Transaction Details:
- ID: {bundle_data.get('transaction_id', 'N/A')}
- Bundle: {bundle_data.get('bundle_id', 'N/A')}

Recommendation: {
    'IMMEDIATE REVIEW REQUIRED' if bundle_data.get('risk_tier') == 'HIGH'
    else 'Secondary verification recommended' if bundle_data.get('risk_tier') == 'BORDERLINE'
    else 'Background observation only'
}
"""
        return description.strip()
    
    def _generate_tags(self, risk_tier: str, detectors: List[str]) -> List[str]:
        """Generate tags for event"""
        
        tags = [f"tier:{risk_tier}"]
        
        if detectors:
            tags.append(f"detectors:{','.join(detectors[:3])}")
        
        if risk_tier == 'HIGH':
            tags.append("requires_immediate_review")
            tags.append("escalation_needed")
        
        return tags