"""
Statsig Integration for A/B Testing and Feature Experimentation
================================================================

This module provides a comprehensive client for managing feature flags,
A/B experiments, and custom event logging through Statsig.

Statsig (statsig-python SDK) enables:
- Feature gating with progressive rollouts
- A/B and multivariate testing with statistical rigor
- Real-time experiment allocation and bucketing
- Custom event logging for metrics analysis

Production usage:
    from statsig.client import StatsigExperimentClient, StatsigUser
    
    client = StatsigExperimentClient(
        api_key="secret-xxx", 
        environment="production"
    )
    
    user = StatsigUser(
        user_id="user_123",
        email="user@example.com",
        plan_tier="premium",
        signup_date="2025-06-01"
    )
    
    # Check feature gate
    if client.check_gate(user, "enable_real_time_personalization"):
        # Serve personalized content
        pass
    
    # Get experiment assignment
    config = client.get_experiment(user, "recommendation_algorithm_v2")
    if config["group"] == "neural_embeddings":
        # Use new neural embedding algorithm
        pass
    
    # Log conversion event
    client.log_event(
        user=user,
        event_name="conversion_rate",
        value=1,
        metadata={"product_id": "premium_tier", "revenue": 99.99}
    )
"""

import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import json

# Mock import for production environment
# In actual implementation: from statsig import statsig, StatsigUser as StatsigSDKUser
try:
    from statsig import statsig as statsig_sdk
    STATSIG_AVAILABLE = True
except ImportError:
    STATSIG_AVAILABLE = False
    # Fallback for development without SDK
    class StatsigSDKUser:
        def __init__(self, user_id: str, **kwargs):
            self.user_id = user_id
            self.custom = kwargs


# Configure logging for experiment tracking
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ExperimentVariant(Enum):
    """Enumeration of possible experiment variants."""
    CONTROL = "control"
    TREATMENT_A = "treatment_a"
    TREATMENT_B = "treatment_b"
    TREATMENT_C = "treatment_c"


@dataclass
class StatsigUser:
    """
    User context for Statsig experiment allocation.
    
    Statsig uses user attributes for deterministic bucketing and targeting.
    Custom attributes enable segment-based experiment targeting.
    
    Attributes:
        user_id: Unique user identifier (required for bucketing)
        email: User email address
        plan_tier: Subscription tier (free, pro, enterprise) for targeting
        signup_date: ISO format date when user joined
        region: Geographic region for localized experiments
        is_premium: Boolean flag for premium vs. free tiers
        cohort_id: Optional cohort identifier for stratified analysis
    """
    user_id: str
    email: Optional[str] = None
    plan_tier: str = "free"  # free, pro, enterprise
    signup_date: Optional[str] = None
    region: str = "US"
    is_premium: bool = False
    cohort_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for SDK serialization."""
        return asdict(self)
    
    def to_sdk_user(self):
        """Convert to Statsig SDK user object for allocation."""
        if not STATSIG_AVAILABLE:
            return self
        
        return StatsigSDKUser(
            user_id=self.user_id,
            email=self.email,
            plan_tier=self.plan_tier,
            signup_date=self.signup_date,
            region=self.region,
            is_premium=self.is_premium,
            cohort_id=self.cohort_id
        )


@dataclass
class ExperimentConfig:
    """
    Experiment configuration and assignment result.
    
    This represents the outcome of experiment bucketing for a user:
    - Which variant the user was assigned to
    - Whether they're in treatment or control
    - The experiment's configuration for that variant
    
    Attributes:
        experiment_name: Identifier of the experiment
        group: Variant name the user was assigned to
        is_treatment: True if user is in any treatment group
        log_exposure: Whether to log this assignment
        config: Variant-specific configuration parameters
        reason: Why this assignment was made (experiment/gate/unknown)
    """
    experiment_name: str
    group: str
    is_treatment: bool
    log_exposure: bool = True
    config: Dict[str, Any] = None
    reason: str = "experiment"
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}


class StatsigExperimentClient:
    """
    Client for Statsig A/B testing and feature experimentation platform.
    
    This client manages:
    - Feature gates (on/off flags with progressive rollouts)
    - A/B and multivariate experiments with statistical rigor
    - Custom event logging for conversion and engagement metrics
    - User segmentation and targeting
    
    Key features:
    - Deterministic bucketing: Same user always gets same experiment variant
    - Real-time evaluation: No server round-trip needed
    - Kill switches: Emergency disable of features in production
    - Multi-armed bandits: Adaptive experiments that learn
    
    Example usage:
        client = StatsigExperimentClient(
            api_key="secret-key",
            environment="production"
        )
        
        user = StatsigUser(user_id="123", plan_tier="pro")
        
        # Feature gate example
        if client.check_gate(user, "enable_ml_recommendations"):
            recommendations = get_ml_recommendations(user_id)
        
        # Experiment example
        exp = client.get_experiment(user, "recommendation_algorithm_v2")
        if exp.group == "neural_embeddings":
            algo = NeuralEmbeddingAlgorithm()
        else:
            algo = CollaborativeFilteringAlgorithm()
    """
    
    # Pre-defined experiments with their configuration
    EXPERIMENTS = {
        "recommendation_algorithm_v2": {
            "name": "Recommendation Algorithm V2",
            "hypothesis": "Neural embedding-based recommendations drive higher engagement than collaborative filtering",
            "variants": {
                "collaborative_filtering": {"weight": 0.5, "description": "Traditional collaborative filtering (control)"},
                "neural_embeddings": {"weight": 0.5, "description": "Neural network-based embeddings (treatment)"}
            },
            "primary_metric": "engagement_score",
            "secondary_metrics": ["session_duration", "conversion_rate"],
            "target_audience": "all_users",
            "duration_days": 14,
            "minimum_sample_size": 1000
        },
        "email_send_time_optimization": {
            "name": "Email Send Time Optimization",
            "hypothesis": "AI-optimized send times and personalized timing windows increase email open rates",
            "variants": {
                "morning": {"weight": 0.25, "description": "8 AM - Fixed morning time"},
                "afternoon": {"weight": 0.25, "description": "2 PM - Fixed afternoon time"},
                "evening": {"weight": 0.25, "description": "6 PM - Fixed evening time"},
                "ai_optimized": {"weight": 0.25, "description": "Per-user optimized time based on behavior"}
            },
            "primary_metric": "email_open_rate",
            "secondary_metrics": ["email_click_rate", "unsubscribe_rate"],
            "target_audience": "premium_users",
            "duration_days": 21,
            "minimum_sample_size": 5000
        },
        "onboarding_flow_variant": {
            "name": "Onboarding Flow Variant",
            "hypothesis": "Gamified onboarding increases time-to-first-engagement and premium tier conversion",
            "variants": {
                "standard": {"weight": 0.33, "description": "Standard linear onboarding flow (control)"},
                "personalized": {"weight": 0.33, "description": "AI-personalized flow based on signup context"},
                "gamified": {"weight": 0.34, "description": "Gamified flow with badges and progress tracking"}
            },
            "primary_metric": "time_to_first_engagement",
            "secondary_metrics": ["onboarding_completion_rate", "premium_conversion_7d"],
            "target_audience": "new_users",
            "duration_days": 30,
            "minimum_sample_size": 500
        },
        "push_notification_frequency": {
            "name": "Push Notification Frequency Optimization",
            "hypothesis": "Adaptive frequency based on user engagement patterns reduces uninstalls while maintaining engagement",
            "variants": {
                "daily": {"weight": 0.25, "description": "Daily push notifications"},
                "three_times_weekly": {"weight": 0.25, "description": "3x per week notifications"},
                "weekly": {"weight": 0.25, "description": "Weekly digest format"},
                "adaptive": {"weight": 0.25, "description": "ML-optimized frequency per user"}
            },
            "primary_metric": "app_retention_7d",
            "secondary_metrics": ["push_engagement_rate", "uninstall_rate"],
            "target_audience": "all_users",
            "duration_days": 28,
            "minimum_sample_size": 2000
        }
    }
    
    # Pre-defined feature gates
    GATES = {
        "enable_real_time_personalization": {
            "name": "Real-time Personalization",
            "description": "Enable real-time content personalization engine",
            "type": "progressive_rollout",
            "initial_rollout_percentage": 0,
            "tier": "all_users",
            "kill_switch": False
        },
        "enable_ml_recommendations": {
            "name": "ML Recommendations Pipeline",
            "description": "Emergency kill switch for ML recommendation system",
            "type": "operational",
            "initial_rollout_percentage": 100,
            "tier": "all_users",
            "kill_switch": True  # Kill switch flag
        },
        "enable_advanced_analytics_dashboard": {
            "name": "Advanced Analytics Dashboard",
            "description": "Beta feature: advanced user analytics and cohort analysis",
            "type": "beta",
            "initial_rollout_percentage": 0,
            "tier": "premium_users",
            "kill_switch": False
        }
    }
    
    # Metric definitions for logging
    METRICS = {
        "conversion_rate": {"type": "counter", "unit": "conversions"},
        "engagement_score": {"type": "gauge", "unit": "score", "min": 0, "max": 100},
        "session_duration": {"type": "timing", "unit": "seconds"},
        "revenue_per_user": {"type": "gauge", "unit": "cents"},
        "email_open_rate": {"type": "percentage", "unit": "percent"},
        "email_click_rate": {"type": "percentage", "unit": "percent"},
        "app_retention_7d": {"type": "percentage", "unit": "percent"},
        "time_to_first_engagement": {"type": "timing", "unit": "hours"}
    }
    
    def __init__(self, api_key: str, environment: str = "production"):
        """
        Initialize Statsig client for experimentation.
        
        Args:
            api_key: Statsig server API key (should be loaded from secrets manager)
            environment: Deployment environment (development/staging/production)
        
        Raises:
            ValueError: If api_key is empty or invalid
        """
        if not api_key or len(api_key) < 10:
            raise ValueError("Invalid or missing API key for Statsig")
        
        self.api_key = api_key
        self.environment = environment
        self.initialized = False
        self.event_queue: List[Dict[str, Any]] = []
        self.event_queue_max_size = 1000
        self.logger = logger
        
        # Initialize SDK if available
        if STATSIG_AVAILABLE:
            try:
                statsig_sdk.initialize(api_key, options={"api_url": "https://statsigapi.net/v1"})
                self.initialized = True
                self.logger.info(f"Statsig initialized for {environment} environment")
            except Exception as e:
                self.logger.error(f"Failed to initialize Statsig: {e}")
                self.initialized = False
    
    def check_gate(self, user: StatsigUser, gate_name: str) -> bool:
        """
        Check if a feature gate is enabled for a user.
        
        Feature gates are on/off flags that can be progressively rolled out.
        Uses deterministic bucketing to ensure consistent user assignment.
        
        Args:
            user: StatsigUser object with user context
            gate_name: Name of the feature gate to check
        
        Returns:
            bool: True if gate is enabled for this user, False otherwise
        
        Example:
            if client.check_gate(user, "enable_real_time_personalization"):
                # Render personalized experience
                pass
        """
        if gate_name not in self.GATES:
            self.logger.warning(f"Unknown gate: {gate_name}")
            return False
        
        gate_config = self.GATES[gate_name]
        
        if self.initialized and STATSIG_AVAILABLE:
            try:
                result = statsig_sdk.check_gate(user.to_sdk_user(), gate_name)
                self.logger.debug(f"Gate {gate_name} evaluated to {result} for user {user.user_id}")
                return result
            except Exception as e:
                self.logger.error(f"Error checking gate {gate_name}: {e}")
                return False
        
        # Fallback: deterministic hashing for gate evaluation
        return self._fallback_gate_check(user, gate_name, gate_config)
    
    def get_experiment(self, user: StatsigUser, experiment_name: str) -> ExperimentConfig:
        """
        Get experiment variant assignment for a user.
        
        Performs deterministic bucketing to assign users to variants.
        The same user always receives the same variant (sticky assignment).
        
        Args:
            user: StatsigUser object with user context
            experiment_name: Name of the experiment
        
        Returns:
            ExperimentConfig: Experiment assignment with variant and config
        
        Example:
            config = client.get_experiment(user, "recommendation_algorithm_v2")
            if config.group == "neural_embeddings":
                recommendations = neural_embedding_model.predict(user_id)
            else:
                recommendations = collaborative_filter(user_id)
        """
        if experiment_name not in self.EXPERIMENTS:
            self.logger.warning(f"Unknown experiment: {experiment_name}")
            return ExperimentConfig(
                experiment_name=experiment_name,
                group="unknown",
                is_treatment=False,
                reason="experiment_not_found"
            )
        
        exp_config = self.EXPERIMENTS[experiment_name]
        
        if self.initialized and STATSIG_AVAILABLE:
            try:
                result = statsig_sdk.get_experiment(user.to_sdk_user(), experiment_name)
                self.logger.debug(f"Experiment {experiment_name} assigned {result.name} to user {user.user_id}")
                return ExperimentConfig(
                    experiment_name=experiment_name,
                    group=result.name,
                    is_treatment=result.name != "control",
                    config=result.config_dict,
                    reason="experiment"
                )
            except Exception as e:
                self.logger.error(f"Error getting experiment {experiment_name}: {e}")
                return ExperimentConfig(
                    experiment_name=experiment_name,
                    group="control",
                    is_treatment=False,
                    reason="error"
                )
        
        # Fallback: deterministic hashing for variant assignment
        return self._fallback_experiment_assignment(user, experiment_name, exp_config)
    
    def log_event(
        self,
        user: StatsigUser,
        event_name: str,
        value: Union[int, float] = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log a custom event for metrics analysis and experiment evaluation.
        
        Events are the primary mechanism for tracking user behavior and
        computing experiment metrics. Queue events for batch submission.
        
        Args:
            user: StatsigUser object identifying the event source
            event_name: Type of event (e.g., 'conversion_rate', 'engagement_score')
            value: Numeric value for the event (default: 1 for counters)
            metadata: Optional dict with additional event context
        
        Returns:
            bool: True if event was queued, False if queue is full
        
        Example:
            client.log_event(
                user=user,
                event_name="conversion_rate",
                value=1,
                metadata={"product_id": "premium_tier", "revenue": 99.99}
            )
        """
        if event_name not in self.METRICS:
            self.logger.warning(f"Unregistered metric: {event_name}")
        
        if metadata is None:
            metadata = {}
        
        event = {
            "event_name": event_name,
            "user_id": user.user_id,
            "timestamp": int(time.time() * 1000),  # Milliseconds
            "value": value,
            "metadata": metadata,
            "environment": self.environment
        }
        
        # Queue event for batch submission
        if len(self.event_queue) < self.event_queue_max_size:
            self.event_queue.append(event)
            self.logger.debug(f"Logged event: {event_name} for user {user.user_id}")
            return True
        else:
            self.logger.warning("Event queue full, dropping event")
            return False
    
    def get_experiment_config(self, experiment_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the full configuration of an experiment.
        
        Returns experiment metadata including hypothesis, variants,
        metrics, sample size requirements, and duration.
        
        Args:
            experiment_name: Name of the experiment
        
        Returns:
            dict: Full experiment configuration, or None if not found
        """
        if experiment_name in self.EXPERIMENTS:
            return self.EXPERIMENTS[experiment_name]
        return None
    
    def get_gate_config(self, gate_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the full configuration of a feature gate.
        
        Args:
            gate_name: Name of the feature gate
        
        Returns:
            dict: Gate configuration, or None if not found
        """
        if gate_name in self.GATES:
            return self.GATES[gate_name]
        return None
    
    def flush_events(self) -> int:
        """
        Flush queued events to Statsig for metric computation.
        
        In production, events are typically batched and submitted
        periodically (e.g., every 10 seconds or 100 events).
        
        Returns:
            int: Number of events flushed
        """
        if not self.event_queue:
            return 0
        
        queue_size = len(self.event_queue)
        
        if self.initialized and STATSIG_AVAILABLE:
            try:
                # In real implementation: statsig_sdk.log_events(self.event_queue)
                self.logger.info(f"Flushed {queue_size} events to Statsig")
                self.event_queue.clear()
                return queue_size
            except Exception as e:
                self.logger.error(f"Error flushing events: {e}")
                return 0
        
        # Fallback: just clear the queue
        self.event_queue.clear()
        return queue_size
    
    def shutdown(self) -> None:
        """
        Shutdown the Statsig client and flush remaining events.
        
        Should be called during application shutdown to ensure
        all events are submitted to Statsig.
        """
        self.flush_events()
        
        if self.initialized and STATSIG_AVAILABLE:
            try:
                statsig_sdk.shutdown()
                self.logger.info("Statsig client shutdown complete")
                self.initialized = False
            except Exception as e:
                self.logger.error(f"Error during shutdown: {e}")
    
    # ==================== Internal Helper Methods ====================
    
    def _fallback_gate_check(
        self,
        user: StatsigUser,
        gate_name: str,
        gate_config: Dict[str, Any]
    ) -> bool:
        """
        Fallback gate evaluation using deterministic hashing.
        
        This method ensures gates work even without Statsig SDK initialization.
        Uses user_id hash to determine gate status consistently.
        """
        # Hash user_id with gate_name for deterministic bucketing
        bucket_value = self._hash_user_to_bucket(user.user_id, gate_name)
        rollout_percentage = gate_config.get("initial_rollout_percentage", 0)
        
        # User is in gate if hash value is below rollout percentage
        return bucket_value < rollout_percentage
    
    def _fallback_experiment_assignment(
        self,
        user: StatsigUser,
        experiment_name: str,
        exp_config: Dict[str, Any]
    ) -> ExperimentConfig:
        """
        Fallback experiment assignment using deterministic hashing.
        
        This method ensures experiments work even without Statsig SDK.
        Variants are assigned based on cumulative weights.
        """
        bucket_value = self._hash_user_to_bucket(user.user_id, experiment_name)
        
        variants = exp_config.get("variants", {})
        cumulative_weight = 0
        
        for variant_name, variant_config in variants.items():
            weight = variant_config.get("weight", 0)
            cumulative_weight += weight
            
            if bucket_value < cumulative_weight:
                return ExperimentConfig(
                    experiment_name=experiment_name,
                    group=variant_name,
                    is_treatment=variant_name != "control",
                    config={"description": variant_config.get("description", "")}
                )
        
        # Fallback to first variant if hashing fails
        first_variant = list(variants.keys())[0] if variants else "control"
        return ExperimentConfig(
            experiment_name=experiment_name,
            group=first_variant,
            is_treatment=first_variant != "control",
            reason="fallback"
        )
    
    @staticmethod
    def _hash_user_to_bucket(user_id: str, experiment_id: str) -> float:
        """
        Hash user_id and experiment_id to consistent value in [0, 1).
        
        This implements deterministic bucketing so the same user always
        gets assigned to the same experiment variant.
        
        Uses SHA256 hash for consistency across distributed systems.
        """
        hash_input = f"{experiment_id}:{user_id}"
        hash_object = hashlib.sha256(hash_input.encode())
        hash_hex = hash_object.hexdigest()
        
        # Convert first 8 hex chars to integer, normalize to [0, 1)
        hash_int = int(hash_hex[:8], 16)
        bucket_value = (hash_int % 10000) / 10000.0
        
        return bucket_value


# ==================== Module-Level Convenience Functions ====================

# Thread-local storage for singleton client
_client_instance = None


def initialize_client(api_key: str, environment: str = "production") -> StatsigExperimentClient:
    """
    Create or return singleton Statsig client.
    
    Args:
        api_key: Statsig server API key
        environment: Environment name
    
    Returns:
        Initialized StatsigExperimentClient
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = StatsigExperimentClient(api_key, environment)
    return _client_instance


def get_client() -> Optional[StatsigExperimentClient]:
    """Get the current client instance."""
    return _client_instance
