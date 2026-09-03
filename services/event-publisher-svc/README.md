# Event Publisher Service

The Event Publisher Service is responsible for processing evidence bundles, generating risk events, managing priority queues, and sending alerts/notifications.

## Features

- Consumes evidence bundles from Redis streams
- Generates risk events with appropriate priority levels
- Manages priority queues (CRITICAL, HIGH, MEDIUM, LOW, BACKGROUND)
- Sends alerts via multiple channels (Slack, Email, Webhooks)
- Creates cases for high and borderline risk events
- Integrates with Kafka for enterprise messaging
- Provides REST API for event management
- Includes rate limiting and alert cooldown mechanisms

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Evidence Bundle Service                       │
│                         (Port 8005)                             │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  bundle.events stream                               │      │
│  │  {event_type: "bundle_ready", ...}                  │      │
│  └──────────────────────┬───────────────────────────────┘      │
└─────────────────────────┼──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Event Publisher Service                       │
│                         (Port 8006)                             │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  1. Consume bundle.events                           │      │
│  │  2. Create Risk Event                               │      │
│  │  3. Determine Priority                              │      │
│  │  4. Publish to streams:                             │      │
│  │     • risk.events (all)                             │      │
│  │     • risk.priority (priority queue)                │      │
│  │  5. Create Case (if HIGH/BORDERLINE)                │      │
│  │  6. Generate Alerts                                 │      │
│  │  7. Send Notifications                              │      │
│  │  8. Publish to Kafka (optional)                     │      │
│  │  9. Dispatch Webhooks (optional)                    │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┬──────────────────┐
        │                 │                 │                  │
        ▼                 ▼                 ▼                  ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  Priority     │ │   Alert/      │ │   Case        │ │   External    │
│  Queues       │ │   Notify      │ │   Management  │ │   Systems     │
│               │ │               │ │               │ │               │
│ • Critical    │ │ • Slack       │ │ • Case DB     │ │ • Kafka       │
│ • High        │ │ • Email       │ │ • Status      │ │ • Webhooks    │
│ • Medium      │ │ • Webhooks    │ │ • Workflow    │ │ • Email       │
│ • Low         │ │               │ │               │ │               │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
```

## Installation

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp .env.example .env.event
   # Edit .env.event with your settings
   ```

4. Run the service:
   ```bash
   python main.py
   ```

## API Endpoints

- `GET /health` - Health check
- `GET /api/v1/events/{event_id}` - Get event by ID
- `GET /api/v1/events/transaction/{transaction_id}` - Get events for transaction
- `POST /api/v1/events/publish` - Manually publish risk event
- `GET /api/v1/events/priority/queue` - Get priority queue status
- `GET /api/v1/events/priority/queue/{priority}` - Dequeue item from priority queue
- `POST /api/v1/events/priority/move/{event_id}` - Move event to different priority queue
- `GET /api/v1/events/stats` - Get event statistics
- `POST /api/v1/events/alert/test/{event_id}` - Test alert system

## Configuration

See `.env.example` for all configuration options.

Key sections:
- Service settings (name, port, debug)
- Database and Redis connections
- Stream names and consumer groups
- Priority queue names
- Alert thresholds and cooldown
- Notification channel settings (Slack, Email, Webhooks)
- Kafka integration (optional)
- Performance settings (batch size, timeouts, workers)

## Testing

Run tests with:
```bash
python -m pytest tests/
```