"""
Segment Event Receiver
======================

FastAPI webhook receiver for Segment track/identify events.
Handles event parsing, validation, and downstream queue publication.

Segment events flow through this receiver to:
1. Validate event schema and user properties
2. Route to appropriate downstream processors
3. Publish to Kafka for streaming analytics
4. Log to S3 for batch processing

Production deployment: Docker container on ECS with load balancing.
Expected throughput: 50K+ events/second.

Usage:
    uvicorn segment_receiver:app --host 0.0.0.0 --port 8000

Production Notes (not implemented in this demo):
- Segment Webhook HMAC: Verify inbound webhooks using Segment's shared secret
  and the X-Signature header (HMAC-SHA1). Reject unsigned payloads to prevent
  spoofed events from poisoning the personalization pipeline.
- PII Tokenization: User traits (email, phone, address) should be tokenized
  before storage using a PII vault (e.g., Skyflow, Basis Theory, or a custom
  KMS-backed token service). The personalization engine operates on tokens, and
  only the email/SMS sender resolves tokens at delivery time.
- A/B Statistical Significance: Variant assignment in the demo uses random
  splits. Production should use a proper experimentation framework (Eppo,
  LaunchDarkly, or Statsig) with sequential testing, multiple comparison
  correction, and minimum detectable effect (MDE) calculations.
- Kafka Idempotency: The Kafka producer should use enable.idempotence=true
  and the consumer should track processed event IDs to ensure exactly-once
  semantics — duplicate events must not trigger duplicate personalization actions.
- GDPR/CCPA Compliance: Implement a user deletion webhook handler that
  purges all PII from Kafka topics, S3 logs, and the feature store within
  the 30-day GDPR erasure window.
"""

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import logging

# ============================================================================
# LOGGER SETUP
# ============================================================================

logger = logging.getLogger(__name__)

# ============================================================================
# SEGMENT EVENT MODELS
# ============================================================================

class UserContext(BaseModel):
    """User context from Segment identify event."""
    user_id: str = Field(..., description="Unique user identifier")
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: Optional[datetime] = None
    traits: Dict[str, Any] = Field(default_factory=dict)

    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v) < 3:
            raise ValueError('user_id must be at least 3 characters')
        return v


class TrackEvent(BaseModel):
    """Segment track event."""
    user_id: str
    event: str = Field(..., description="Event name (e.g. 'content_completed')")
    properties: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = Field(default_factory=dict)

    @validator('event')
    def validate_event(cls, v):
        """Validate event name is recognized."""
        valid_events = {
            'app_opened',
            'content_started',
            'content_completed',
            'goal_action_taken',
            'social_interaction',
            'notification_dismissed',
            'notification_opted_out',
            'session_started',
            'session_ended'
        }
        if v not in valid_events:
            raise ValueError(f'Unknown event type: {v}')
        return v


class IdentifyEvent(BaseModel):
    """Segment identify event."""
    user_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    traits: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SegmentBatch(BaseModel):
    """Segment batch API payload."""
    batch: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Segment Event Receiver",
    description="Webhook receiver for Segment events with validation and routing",
    version="1.0.0"
)


@app.post("/segment/track")
async def receive_track_event(event: TrackEvent) -> Dict[str, Any]:
    """
    Receive track event from Segment.

    Route to Kafka:
      - Raw events topic (for data lake)
      - Scoring topic (for real-time engagement scoring)
      - Recommendation topic (for collaborative filtering)

    Args:
        event: Validated TrackEvent from Segment

    Returns:
        Acknowledgment with event ID
    """
    try:
        # Log event
        logger.info(f"Track event received: {event.event} from {event.user_id}")

        # In production, would:
        # 1. Publish to Kafka raw-events topic
        # 2. Route to feature computation if meaningful_action
        # 3. Trigger scoring if engagement update needed

        # Validate event properties based on event type
        if event.event == 'content_completed':
            required_props = ['content_id', 'completion_time_seconds', 'difficulty']
            if not all(p in event.properties for p in required_props):
                raise ValueError(f"Missing required properties for content_completed: {required_props}")

        elif event.event == 'social_interaction':
            required_props = ['interaction_type', 'target_user_id']
            if not all(p in event.properties for p in required_props):
                raise ValueError(f"Missing required properties for social_interaction: {required_props}")

        # Extract and validate context
        ip_address = event.context.get('ip')
        device_type = event.context.get('library', {}).get('name')  # ios, android, web

        # Rate limiting (in production, would check Redis)
        # user_events_per_minute = await rate_limiter.check(event.user_id)
        # if user_events_per_minute > 1000:
        #     raise HTTPException(status_code=429, detail="Rate limit exceeded")

        # Build event for downstream
        enriched_event = {
            'segment_id': f"{event.user_id}:{event.timestamp.isoformat()}",
            'user_id': event.user_id,
            'event_type': event.event,
            'properties': event.properties,
            'timestamp': event.timestamp.isoformat(),
            'device_type': device_type,
            'ip_address': ip_address,
            'received_at': datetime.utcnow().isoformat()
        }

        # Publish to Kafka (stubbed)
        # await kafka_producer.send('events-raw', enriched_event)
        # if is_meaningful_action(event.event):
        #     await kafka_producer.send('events-scoring', enriched_event)

        return {
            "status": "success",
            "segment_id": enriched_event['segment_id'],
            "event_type": event.event,
            "user_id": event.user_id
        }

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing track event: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/segment/identify")
async def receive_identify_event(event: IdentifyEvent) -> Dict[str, Any]:
    """
    Receive identify event from Segment.

    Update user profile attributes:
      - Email, phone, demographics
      - Goals, preferences, lifecycle stage
      - Custom traits from app

    Args:
        event: Validated IdentifyEvent from Segment

    Returns:
        Acknowledgment with user ID
    """
    try:
        logger.info(f"Identify event received for user: {event.user_id}")

        # In production:
        # 1. Update user profile in PostgreSQL
        # 2. Invalidate Redis cache for this user
        # 3. Queue for feature recomputation if goals changed

        # Validate trait values
        if 'goal' in event.traits:
            valid_goals = {'weight_loss', 'build_strength', 'improve_flexibility', 'nutrition', 'recovery'}
            goal = event.traits.get('goal')
            if goal and goal not in valid_goals:
                raise ValueError(f"Invalid goal: {goal}")

        if 'lifecycle_stage' in event.traits:
            valid_stages = {'new', 'activated', 'engaged', 'at_risk', 'dormant', 'reactivated'}
            stage = event.traits.get('lifecycle_stage')
            if stage and stage not in valid_stages:
                raise ValueError(f"Invalid lifecycle stage: {stage}")

        # Build user profile update
        profile_update = {
            'user_id': event.user_id,
            'email': event.email,
            'phone': event.phone,
            'traits': event.traits,
            'updated_at': event.timestamp.isoformat()
        }

        # Publish to Kafka (stubbed)
        # await kafka_producer.send('user-profiles', profile_update)

        # Invalidate cache (stubbed)
        # await redis_client.delete(f"user:{event.user_id}")

        return {
            "status": "success",
            "user_id": event.user_id,
            "traits_updated": len(event.traits)
        }

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing identify event: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/segment/batch")
async def receive_batch(batch: SegmentBatch) -> Dict[str, Any]:
    """
    Receive batch of events from Segment.

    Segment sends batches of up to 32 events per request for efficiency.
    Parse and route each event to appropriate handler.

    Args:
        batch: Batch of events from Segment

    Returns:
        Summary of processed events
    """
    try:
        logger.info(f"Batch received with {len(batch.batch)} events")

        processed = {'track': 0, 'identify': 0, 'errors': 0}

        for item in batch.batch:
            try:
                if item.get('type') == 'track':
                    event = TrackEvent(**item)
                    # Process track event
                    processed['track'] += 1
                elif item.get('type') == 'identify':
                    event = IdentifyEvent(**item)
                    # Process identify event
                    processed['identify'] += 1
            except Exception as e:
                logger.error(f"Error processing batch item: {e}")
                processed['errors'] += 1

        return {
            "status": "success",
            "batch_size": len(batch.batch),
            "processed": processed
        }

    except Exception as e:
        logger.error(f"Error processing batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint for load balancer.

    Returns:
        Status and uptime information
    """
    return {
        "status": "healthy",
        "service": "segment-receiver",
        "version": "1.0.0"
    }


@app.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """
    Prometheus metrics endpoint.

    In production, would export:
      - events_received_total (counter by event type)
      - events_processing_seconds (histogram)
      - kafka_publish_errors (counter)
      - rate_limit_hits (counter)

    Returns:
        Metrics in Prometheus text format
    """
    return {
        "message": "Metrics available at /metrics in Prometheus format",
        "note": "In production, would use prometheus-client library"
    }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def is_meaningful_action(event_type: str) -> bool:
    """Determine if event should trigger engagement scoring."""
    meaningful_events = {
        'content_completed',
        'goal_action_taken',
        'social_interaction'
    }
    return event_type in meaningful_events


def enrich_event_context(request: Request, event: TrackEvent) -> Dict[str, Any]:
    """Enrich event with HTTP context."""
    return {
        'ip_address': request.client.host,
        'user_agent': request.headers.get('user-agent'),
        'timestamp_received': datetime.utcnow().isoformat()
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Production config: docker run -e PORT=8000 engagement-receiver
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        workers=4,
        log_level="info"
    )
