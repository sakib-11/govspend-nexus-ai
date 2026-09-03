from typing import List, Dict, Any, Optional
import json
import hashlib
from datetime import datetime, timedelta
import redis.asyncio as redis
from models.events import RiskEvent, Alert, PriorityLevel
from integrations.slack_notifier import SlackNotifier
from integrations.email_notifier import EmailNotifier
from integrations.webhook_dispatcher import WebhookDispatcher

class AlertManager:
    """Manage alerts and notifications"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        config,
        slack_notifier: Optional[SlackNotifier] = None,
        email_notifier: Optional[EmailNotifier] = None,
        webhook_dispatcher: Optional[WebhookDispatcher] = None
    ):
        self.redis = redis_client
        self.config = config
        self.slack_notifier = slack_notifier
        self.email_notifier = email_notifier
        self.webhook_dispatcher = webhook_dispatcher
        
        # Alert tracking (prevent duplicates)
        self.alert_cache_key = "alert_cache"
        self.alert_cooldown = config.alert_cooldown_minutes
    
    async def process_event(self, event: RiskEvent) -> List[Alert]:
        """Process event and generate appropriate alerts"""
        
        alerts = []
        
        # Determine if alert is needed
        if event.risk_tier == "HIGH" and event.risk_score >= self.config.alert_threshold_high:
            alerts.extend(await self._generate_high_risk_alerts(event))
        
        elif event.risk_tier == "BORDERLINE" and event.risk_score >= self.config.alert_threshold_borderline:
            alerts.extend(await self._generate_borderline_alerts(event))
        
        # Always create a case for any non-low risk event
        if event.risk_tier in ["HIGH", "BORDERLINE"]:
            alerts.append(await self._generate_case_alert(event))
        
        return alerts
    
    async def _generate_high_risk_alerts(self, event: RiskEvent) -> List[Alert]:
        """Generate alerts for high risk events"""
        
        alerts = []
        
        # Check cooldown to prevent alert spam
        if await self._check_cooldown(event):
            return alerts
        
        # Priority: CRITICAL for very high risk (>0.90)
        priority = (
            PriorityLevel.CRITICAL 
            if event.risk_score >= 0.90 
            else PriorityLevel.HIGH
        )
        
        # Slack alert
        if self.config.slack_enabled and self.slack_notifier:
            alert = Alert(
                event_id=event.event_id,
                priority=priority,
                alert_type="slack",
                subject=f"🚨 HIGH RISK ALERT: {event.summary}",
                message=self._format_slack_message(event),
                channels=["#risk-alerts", "#fraud-team"]
            )
            alerts.append(alert)
        
        # Email alert
        if self.config.email_enabled and self.email_notifier:
            alert = Alert(
                event_id=event.event_id,
                priority=priority,
                alert_type="email",
                subject=f"HIGH RISK ALERT: Risk Score {event.risk_score:.2%}",
                message=self._format_email_message(event),
                recipients=["fraud-team@example.com", "compliance@example.com"]
            )
            alerts.append(alert)
        
        # Webhook alert
        if self.config.webhook_enabled and self.webhook_dispatcher:
            alert = Alert(
                event_id=event.event_id,
                priority=priority,
                alert_type="webhook",
                subject=f"High Risk: {event.transaction_id}",
                message=json.dumps(event.metadata),
                data=event.metadata
            )
            alerts.append(alert)
        
        return alerts
    
    async def _generate_borderline_alerts(self, event: RiskEvent) -> List[Alert]:
        """Generate alerts for borderline risk events"""
        
        alerts = []
        
        # Check cooldown
        if await self._check_cooldown(event):
            return alerts
        
        # Only send low-priority notifications for borderline
        if self.config.slack_enabled and self.slack_notifier:
            alert = Alert(
                event_id=event.event_id,
                priority=PriorityLevel.MEDIUM,
                alert_type="slack",
                subject=f"⚠️ BORDERLINE RISK: {event.summary}",
                message=self._format_slack_message(event, level="borderline"),
                channels=["#risk-alerts"]
            )
            alerts.append(alert)
        
        return alerts
    
    async def _generate_case_alert(self, event: RiskEvent) -> Alert:
        """Generate case creation alert"""
        
        return Alert(
            event_id=event.event_id,
            priority=event.priority,
            alert_type="case_creation",
            subject=f"Case Created for Transaction {event.transaction_id}",
            message=f"New risk case created for transaction {event.transaction_id} with tier {event.risk_tier}",
            data={
                "case_id": event.case_id,
                "transaction_id": event.transaction_id,
                "risk_tier": event.risk_tier,
                "risk_score": event.risk_score
            }
        )
    
    async def send_alerts(self, alerts: List[Alert]) -> List[Alert]:
        """Send all alerts"""
        
        sent_alerts = []
        
        for alert in alerts:
            try:
                sent = await self._send_alert(alert)
                if sent:
                    alert.sent = True
                    alert.sent_at = datetime.now()
                    sent_alerts.append(alert)
                    
                    # Store in cache for cooldown
                    await self._store_alert_cache(alert)
            except Exception as e:
                alert.error = str(e)
                alert.retry_count += 1
        
        return sent_alerts
    
    async def _send_alert(self, alert: Alert) -> bool:
        """Send individual alert through appropriate channel"""
        
        if alert.alert_type == "slack" and self.slack_notifier:
            return await self.slack_notifier.send(
                message=alert.message,
                channel=alert.channels[0] if alert.channels else None
            )
        
        elif alert.alert_type == "email" and self.email_notifier:
            return await self.email_notifier.send(
                subject=alert.subject,
                body=alert.message,
                recipients=alert.recipients
            )
        
        elif alert.alert_type == "webhook" and self.webhook_dispatcher:
            return await self.webhook_dispatcher.dispatch(
                data=alert.data,
                endpoint=self.config.webhook_endpoints[0] if self.config.webhook_endpoints else None
            )
        
        elif alert.alert_type == "case_creation":
            # Store case creation event, no external notification needed
            return True
        
        return False
    
    async def _check_cooldown(self, event: RiskEvent) -> bool:
        """Check if alert is in cooldown period"""
        
        cache_key = f"alert:{event.transaction_id}:{event.risk_tier}"
        
        last_alert_time = await self.redis.get(cache_key)
        if last_alert_time:
            last_alert = datetime.fromisoformat(last_alert_time)
            cooldown_end = last_alert + timedelta(minutes=self.alert_cooldown)
            
            if datetime.now() < cooldown_end:
                return True  # Still in cooldown
        
        return False
    
    async def _store_alert_cache(self, alert: Alert):
        """Store alert in cache for cooldown tracking"""
        
        cache_key = f"alert:{alert.event_id}:{alert.alert_type}"
        await self.redis.set(
            cache_key,
            datetime.now().isoformat(),
            ex=self.alert_cooldown * 60  # Convert to seconds
        )
    
    def _format_slack_message(self, event: RiskEvent, level: str = "high") -> str:
        """Format Slack message"""
        
        emoji = "🚨" if level == "high" else "⚠️"
        
        message = f"""
{emoji} *RISK ALERT* {emoji}

*Transaction ID:* {event.transaction_id}
*Risk Score:* {event.risk_score:.2%}
*Risk Tier:* {event.risk_tier}
*Priority:* {event.priority.value.upper()}

*Summary:* {event.summary}

*Detectors Triggered:*
{chr(10).join(f"• {d}" for d in event.detectors_triggered)}

*Time:* {event.occurred_at.strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        if event.case_id:
            message += f"\n*Case ID:* {event.case_id}"
        
        return message
    
    def _format_email_message(self, event: RiskEvent) -> str:
        """Format email message"""
        
        return f"""
HIGH RISK ALERT

Transaction: {event.transaction_id}
Risk Score: {event.risk_score:.2%}
Risk Tier: {event.risk_tier}

Summary: {event.summary}

Detectors: {', '.join(event.detectors_triggered)}

Time: {event.occurred_at.strftime('%Y-%m-%d %H:%M:%S')}

This transaction requires immediate review.

---
GovSpend Nexus AI - Risk Detection System
"""