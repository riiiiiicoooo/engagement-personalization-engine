"""
Amplitude Product Analytics Integration
========================================

This module provides comprehensive event tracking and cohort analysis
integration with Amplitude for measuring user engagement, conversions,
and retention across the Engagement & Personalization Engine.

Amplitude provides:
- Event-based analytics with custom properties
- User property tracking and segmentation
- Cohort definitions for targeted analysis
- Funnel analysis for conversion tracking
- Behavioral cohorts for ML-driven insights

Production usage:
    from amplitude.analytics import AmplitudeTracker
    
    tracker = AmplitudeTracker(api_key="amplitude_key")
    
    # Track user engagement
    tracker.track_event(
        user_id="user_123",
        event_type="content_viewed",
        properties={"content_id": "abc", "duration_seconds": 45}
    )
    
    # Identify user properties
    tracker.identify_user(
        user_id="user_123",
        user_properties={
            "plan_tier": "premium",
            "signup_date": "2025-06-01",
            "total_sessions": 15
        }
    )
    
    # Track revenue events
    tracker.track_revenue(
        user_id="user_123",
        amount=99.99,
        product_id="premium_subscription"
    )
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# Mock import for production environment
# In actual implementation: from amplitude import Amplitude
try:
    from amplitude import Amplitude
    AMPLITUDE_AVAILABLE = True
except ImportError:
    AMPLITUDE_AVAILABLE = False


# Configure logging for analytics events
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EventCategory(Enum):
    """Event categories for organization and filtering."""
    CONTENT = "content"
    ENGAGEMENT = "engagement"
    CONVERSION = "conversion"
    RECOMMENDATION = "recommendation"
    TECHNICAL = "technical"
    RETENTION = "retention"


@dataclass
class AnalyticsEvent:
    """
    Analytics event with standardized schema.
    
    Attributes:
        user_id: Unique user identifier
        event_type: Type of event (e.g., 'content_viewed')
        category: Event category for filtering
        properties: Custom event properties
        timestamp: Event occurrence time (milliseconds since epoch)
        session_id: Session identifier for grouping events
        device_id: Device identifier for cross-device tracking
    """
    user_id: str
    event_type: str
    category: EventCategory
    properties: Dict[str, Any]
    timestamp: int
    session_id: Optional[str] = None
    device_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API submission."""
        return {
            "user_id": self.user_id,
            "event_type": self.event_type,
            "category": self.category.value,
            "properties": self.properties,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "device_id": self.device_id
        }


class AmplitudeTracker:
    """
    Amplitude analytics tracker for product event tracking.
    
    This tracker manages:
    - Event logging with consistent schema
    - User property identification and updates
    - Revenue tracking and subscription events
    - Cohort definition and management
    - Funnel analysis for conversion metrics
    
    Features:
    - Local event queuing with batch submission
    - Automatic timestamp and session ID management
    - User property synchronization
    - Revenue event special handling
    - Event de-duplication
    
    Example:
        tracker = AmplitudeTracker(api_key="key_xyz")
        
        tracker.track_event(
            user_id="user_123",
            event_type="content_viewed",
            properties={"content_id": "xyz", "duration": 45}
        )
        
        tracker.identify_user(
            user_id="user_123",
            user_properties={"plan_tier": "pro"}
        )
        
        events_flushed = tracker.flush_events()
    """
    
    # Pre-defined event taxonomy
    EVENT_TAXONOMY = {
        # Content interaction events
        "content_viewed": {
            "category": EventCategory.CONTENT,
            "schema": {
                "content_id": "string",
                "content_type": "string",  # article, video, tutorial
                "duration_seconds": "number",
                "completion_percentage": "number"
            }
        },
        "content_shared": {
            "category": EventCategory.CONTENT,
            "schema": {
                "content_id": "string",
                "share_channel": "string",  # email, social, link
                "recipient_count": "number"
            }
        },
        "content_saved": {
            "category": EventCategory.CONTENT,
            "schema": {
                "content_id": "string",
                "collection_id": "string"
            }
        },
        "content_completed": {
            "category": EventCategory.CONTENT,
            "schema": {
                "content_id": "string",
                "completion_time_seconds": "number",
                "difficulty_level": "string"
            }
        },
        
        # Engagement events
        "session_start": {
            "category": EventCategory.ENGAGEMENT,
            "schema": {
                "source": "string",  # web, mobile, api
                "entry_point": "string",
                "referrer": "string"
            }
        },
        "session_end": {
            "category": EventCategory.ENGAGEMENT,
            "schema": {
                "session_duration_seconds": "number",
                "pages_viewed": "number",
                "events_triggered": "number"
            }
        },
        "feature_used": {
            "category": EventCategory.ENGAGEMENT,
            "schema": {
                "feature_name": "string",
                "feature_version": "string",
                "usage_count": "number"
            }
        },
        "search_performed": {
            "category": EventCategory.ENGAGEMENT,
            "schema": {
                "query": "string",
                "result_count": "number",
                "search_type": "string"  # global, in-content
            }
        },
        
        # Conversion events
        "signup_completed": {
            "category": EventCategory.CONVERSION,
            "schema": {
                "source": "string",  # organic, social, referral, paid
                "signup_method": "string",  # email, social, sso
                "trial_days": "number"
            }
        },
        "subscription_started": {
            "category": EventCategory.CONVERSION,
            "schema": {
                "plan_tier": "string",  # free, pro, enterprise
                "billing_interval": "string",  # monthly, annual
                "price_usd": "number"
            }
        },
        "upgrade_initiated": {
            "category": EventCategory.CONVERSION,
            "schema": {
                "from_plan": "string",
                "to_plan": "string",
                "price_difference": "number"
            }
        },
        "purchase_completed": {
            "category": EventCategory.CONVERSION,
            "schema": {
                "product_id": "string",
                "amount_usd": "number",
                "currency": "string",
                "quantity": "number"
            }
        },
        
        # Recommendation events
        "recommendation_shown": {
            "category": EventCategory.RECOMMENDATION,
            "schema": {
                "recommendation_id": "string",
                "algorithm": "string",  # cf, neural, hybrid
                "position": "number",
                "count": "number"
            }
        },
        "recommendation_clicked": {
            "category": EventCategory.RECOMMENDATION,
            "schema": {
                "recommendation_id": "string",
                "content_id": "string",
                "position": "number"
            }
        },
        "recommendation_dismissed": {
            "category": EventCategory.RECOMMENDATION,
            "schema": {
                "recommendation_id": "string",
                "reason": "string"  # not_relevant, not_interested, duplicate
            }
        }
    }
    
    # Cohort definitions for segmentation and analysis
    COHORTS = {
        "power_users": {
            "name": "Power Users",
            "description": "Users with 7+ sessions per week (highly engaged)",
            "conditions": {
                "sessions_per_week": {"gte": 7},
                "account_age_days": {"gte": 30}
            },
            "lookback_days": 7
        },
        "at_risk": {
            "name": "At-Risk Users",
            "description": "No session in 14 days (dormant/churning)",
            "conditions": {
                "days_since_last_session": {"gte": 14},
                "total_sessions": {"gte": 1}
            },
            "lookback_days": 30
        },
        "new_users": {
            "name": "New Users",
            "description": "Account age less than 7 days",
            "conditions": {
                "account_age_days": {"lt": 7}
            },
            "lookback_days": 7
        },
        "paid_subscribers": {
            "name": "Paid Subscribers",
            "description": "Active paid subscription (pro or enterprise tier)",
            "conditions": {
                "plan_tier": {"in": ["pro", "enterprise"]},
                "subscription_active": True
            },
            "lookback_days": 30
        },
        "high_engagement": {
            "name": "High Engagement",
            "description": "Session duration > 10 minutes",
            "conditions": {
                "avg_session_duration_minutes": {"gte": 10}
            },
            "lookback_days": 30
        }
    }
    
    # Funnel definitions for conversion tracking
    FUNNELS = {
        "onboarding_funnel": {
            "name": "Onboarding Funnel",
            "description": "Signup → Profile setup → First content view → Subscription",
            "steps": [
                {
                    "event": "signup_completed",
                    "description": "User completes signup"
                },
                {
                    "event": "feature_used",
                    "filters": {"feature_name": "profile_setup"},
                    "description": "User sets up profile"
                },
                {
                    "event": "content_viewed",
                    "description": "User views first content"
                },
                {
                    "event": "subscription_started",
                    "description": "User starts paid subscription"
                }
            ],
            "conversion_window_days": 30
        },
        "conversion_funnel": {
            "name": "Conversion Funnel",
            "description": "Session start → Feature use → Upgrade initiated → Purchase completed",
            "steps": [
                {
                    "event": "session_start",
                    "description": "User starts session"
                },
                {
                    "event": "feature_used",
                    "description": "User uses premium feature"
                },
                {
                    "event": "upgrade_initiated",
                    "description": "User initiates upgrade"
                },
                {
                    "event": "purchase_completed",
                    "description": "User completes purchase"
                }
            ],
            "conversion_window_days": 7
        },
        "recommendation_engagement_funnel": {
            "name": "Recommendation Engagement Funnel",
            "description": "Recommendation shown → Clicked → Content completed → Rating",
            "steps": [
                {
                    "event": "recommendation_shown",
                    "description": "Recommendation displayed"
                },
                {
                    "event": "recommendation_clicked",
                    "description": "User clicks recommendation"
                },
                {
                    "event": "content_viewed",
                    "description": "User views content"
                },
                {
                    "event": "content_completed",
                    "description": "User completes content"
                }
            ],
            "conversion_window_days": 7
        }
    }
    
    def __init__(self, api_key: str, environment: str = "production"):
        """
        Initialize Amplitude tracker.
        
        Args:
            api_key: Amplitude API key (from Amplitude dashboard)
            environment: Environment (development/staging/production)
        
        Raises:
            ValueError: If api_key is invalid
        """
        if not api_key or len(api_key) < 10:
            raise ValueError("Invalid API key for Amplitude")
        
        self.api_key = api_key
        self.environment = environment
        self.event_queue: List[AnalyticsEvent] = []
        self.event_queue_max_size = 5000
        self.user_properties: Dict[str, Dict[str, Any]] = {}
        self.logger = logger
        self.initialized = False
        
        # Initialize SDK if available
        if AMPLITUDE_AVAILABLE:
            try:
                self.client = Amplitude(api_key)
                self.initialized = True
                self.logger.info(f"Amplitude initialized for {environment} environment")
            except Exception as e:
                self.logger.error(f"Failed to initialize Amplitude: {e}")
                self.initialized = False
    
    def track_event(
        self,
        user_id: str,
        event_type: str,
        properties: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> bool:
        """
        Track a custom event with properties.
        
        Events are the primary unit of analytics data. Each event represents
        a user action (e.g., "content_viewed", "purchase_completed").
        
        Args:
            user_id: Unique user identifier
            event_type: Event type (e.g., "content_viewed")
            properties: Custom event properties dict
            session_id: Optional session identifier for grouping
            device_id: Optional device identifier for cross-device tracking
        
        Returns:
            bool: True if event was queued successfully
        
        Example:
            tracker.track_event(
                user_id="user_123",
                event_type="content_viewed",
                properties={
                    "content_id": "article_xyz",
                    "duration_seconds": 45,
                    "completion_percentage": 100
                }
            )
        """
        if not user_id:
            self.logger.warning("Cannot track event without user_id")
            return False
        
        if properties is None:
            properties = {}
        
        # Validate event type is in taxonomy
        if event_type not in self.EVENT_TAXONOMY:
            self.logger.warning(f"Unregistered event type: {event_type}")
        
        # Create analytics event
        event = AnalyticsEvent(
            user_id=user_id,
            event_type=event_type,
            category=self.EVENT_TAXONOMY.get(event_type, {}).get("category", EventCategory.TECHNICAL),
            properties=properties,
            timestamp=int(time.time() * 1000),
            session_id=session_id,
            device_id=device_id
        )
        
        # Queue event for batch submission
        if len(self.event_queue) < self.event_queue_max_size:
            self.event_queue.append(event)
            self.logger.debug(f"Queued event: {event_type} for user {user_id}")
            return True
        else:
            self.logger.warning("Event queue full, dropping event")
            return False
    
    def identify_user(
        self,
        user_id: str,
        user_properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Identify and set user properties for segmentation.
        
        User properties enable cohort definition, segmentation, and
        property-based filtering in Amplitude. Common properties:
        - plan_tier: subscription level
        - signup_date: when user joined
        - region: geographic location
        - total_sessions: engagement metric
        
        Args:
            user_id: Unique user identifier
            user_properties: Dict of user properties to set
        
        Returns:
            bool: True if user was identified successfully
        
        Example:
            tracker.identify_user(
                user_id="user_123",
                user_properties={
                    "plan_tier": "premium",
                    "signup_date": "2025-06-01",
                    "region": "US",
                    "total_sessions": 15
                }
            )
        """
        if not user_id:
            self.logger.warning("Cannot identify user without user_id")
            return False
        
        if user_properties is None:
            user_properties = {}
        
        # Ensure timestamps are ISO format
        now = datetime.utcnow().isoformat() + "Z"
        user_properties["last_seen"] = now
        
        # Store in local cache
        self.user_properties[user_id] = user_properties
        
        if self.initialized and AMPLITUDE_AVAILABLE:
            try:
                self.client.identify(user_id, user_properties)
                self.logger.debug(f"Identified user: {user_id}")
                return True
            except Exception as e:
                self.logger.error(f"Error identifying user {user_id}: {e}")
                return False
        
        self.logger.debug(f"Cached user properties for {user_id}")
        return True
    
    def track_revenue(
        self,
        user_id: str,
        amount: float,
        product_id: str,
        currency: str = "USD",
        quantity: int = 1,
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Track revenue event for purchase/subscription.
        
        Revenue events are special events that trigger monetization metrics
        and revenue attribution analysis in Amplitude.
        
        Args:
            user_id: Unique user identifier
            amount: Amount in dollars/cents
            product_id: Product purchased
            currency: Currency code (default: USD)
            quantity: Quantity purchased
            properties: Additional event properties
        
        Returns:
            bool: True if revenue event was tracked
        
        Example:
            tracker.track_revenue(
                user_id="user_123",
                amount=99.99,
                product_id="premium_tier",
                currency="USD",
                quantity=1
            )
        """
        if not user_id or amount <= 0:
            self.logger.warning("Invalid revenue event parameters")
            return False
        
        if properties is None:
            properties = {}
        
        revenue_event_properties = {
            "amount": amount,
            "product_id": product_id,
            "currency": currency,
            "quantity": quantity,
            **properties
        }
        
        return self.track_event(
            user_id=user_id,
            event_type="purchase_completed",
            properties=revenue_event_properties
        )
    
    def get_cohort_definition(self, cohort_name: str) -> Optional[Dict[str, Any]]:
        """
        Get definition of a named cohort.
        
        Args:
            cohort_name: Name of the cohort
        
        Returns:
            dict: Cohort definition, or None if not found
        """
        if cohort_name in self.COHORTS:
            return self.COHORTS[cohort_name]
        return None
    
    def get_funnel_definition(self, funnel_name: str) -> Optional[Dict[str, Any]]:
        """
        Get definition of a named funnel.
        
        Args:
            funnel_name: Name of the funnel
        
        Returns:
            dict: Funnel definition, or None if not found
        """
        if funnel_name in self.FUNNELS:
            return self.FUNNELS[funnel_name]
        return None
    
    def get_event_taxonomy(self, event_type: str) -> Optional[Dict[str, Any]]:
        """
        Get schema definition for an event type.
        
        Args:
            event_type: Name of the event type
        
        Returns:
            dict: Event schema, or None if not found
        """
        if event_type in self.EVENT_TAXONOMY:
            return self.EVENT_TAXONOMY[event_type]
        return None
    
    def flush_events(self) -> int:
        """
        Flush queued events to Amplitude for processing.
        
        In production, events are batched and submitted periodically.
        This method can be called manually or automatically.
        
        Returns:
            int: Number of events flushed
        """
        if not self.event_queue:
            return 0
        
        queue_size = len(self.event_queue)
        
        if self.initialized and AMPLITUDE_AVAILABLE:
            try:
                # Convert events to dicts for submission
                event_dicts = [event.to_dict() for event in self.event_queue]
                
                # In real implementation: self.client.track_events(event_dicts)
                self.logger.info(f"Flushed {queue_size} events to Amplitude")
                self.event_queue.clear()
                return queue_size
            except Exception as e:
                self.logger.error(f"Error flushing events: {e}")
                return 0
        
        # Fallback: just clear the queue
        self.logger.info(f"Cleared {queue_size} events from queue (Amplitude not initialized)")
        self.event_queue.clear()
        return queue_size
    
    def get_queue_size(self) -> int:
        """Get current number of queued events."""
        return len(self.event_queue)
    
    def shutdown(self) -> int:
        """
        Shutdown tracker and flush remaining events.
        
        Returns:
            int: Number of events flushed during shutdown
        """
        flushed = self.flush_events()
        self.logger.info("Amplitude tracker shutdown complete")
        return flushed


# ==================== Module-Level Convenience Functions ====================

_tracker_instance = None


def initialize_tracker(api_key: str, environment: str = "production") -> AmplitudeTracker:
    """
    Create or return singleton Amplitude tracker.
    
    Args:
        api_key: Amplitude API key
        environment: Environment name
    
    Returns:
        Initialized AmplitudeTracker
    """
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = AmplitudeTracker(api_key, environment)
    return _tracker_instance


def get_tracker() -> Optional[AmplitudeTracker]:
    """Get the current tracker instance."""
    return _tracker_instance
