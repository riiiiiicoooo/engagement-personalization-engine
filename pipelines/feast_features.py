"""
Feast Feature Definitions
==========================

Feature store definitions for the Engagement & Personalization Engine.
Integrates with Snowflake as data source and Redis for online serving.

Features are organized into feature views:
1. Engagement Features: Real-time user engagement metrics
2. Churn Risk Features: Indicators of imminent churn
3. Recommendation Features: For personalization models
4. User Profile Features: Static/semi-static user attributes

Production setup:
    - Offline: Snowflake (for training/batch scoring)
    - Online: Redis (for real-time serving, <100ms latency)
    - Registry: local.db (development) or cloud storage (production)

Usage:
    feast apply             # Deploy features to registry
    feast materialize       # Sync offline → online store
    feast ui                # Launch feature store UI
"""

from datetime import timedelta
from feast import (
    FeatureStore,
    FeatureView,
    FeatureService,
    Field,
    Entity,
    ValueType,
    SnowflakeSource,
    Online,
    Offline,
    DeltaSource,
    FileSource
)
from feast.infra.online_stores.redis import RedisOnlineStore
from feast.infra.offline_stores.snowflake import SnowflakeOfflineStore
from feast.types import Float32, Float64, Int32, Int64, String, Bool


# ============================================================================
# ENTITIES
# ============================================================================

user = Entity(
    name="user_id",
    value_type=ValueType.STRING,
    description="Unique user identifier"
)

content = Entity(
    name="content_id",
    value_type=ValueType.STRING,
    description="Unique content item identifier"
)


# ============================================================================
# DATA SOURCES
# ============================================================================

# Snowflake connections for offline store
engagement_features_snowflake = SnowflakeSource(
    name="engagement_features_snowflake",
    database="analytics",
    schema="features",
    table="engagement_features_daily",
    timestamp_field="feature_date",
    created_timestamp_column="created_at",
    field_mapping={
        "user_id": "user_id",
        "feature_date": "feature_date"
    }
)

churn_features_snowflake = SnowflakeSource(
    name="churn_features_snowflake",
    database="analytics",
    schema="features",
    table="churn_features_daily",
    timestamp_field="feature_date",
    created_timestamp_column="created_at",
    field_mapping={
        "user_id": "user_id",
        "feature_date": "feature_date"
    }
)

recommendation_features_snowflake = SnowflakeSource(
    name="recommendation_features_snowflake",
    database="analytics",
    schema="features",
    table="recommendation_features_daily",
    timestamp_field="feature_date",
    created_timestamp_column="created_at"
)

user_profile_snowflake = SnowflakeSource(
    name="user_profile_snowflake",
    database="analytics",
    schema="segment",
    table="users",
    timestamp_field="updated_at",
    created_timestamp_column="created_at"
)


# ============================================================================
# FEATURE VIEWS: ENGAGEMENT METRICS
# ============================================================================

engagement_features_view = FeatureView(
    name="engagement_features",
    description="Real-time user engagement metrics (14-day trailing window)",
    entities=[user],
    ttl=timedelta(hours=24),  # Refresh daily
    online=True,
    offline=True,
    source=engagement_features_snowflake,
    tags={"team": "personalization", "domain": "engagement"},
    features=[
        Field(name="sessions_per_week_14d", dtype=Float32,
              description="Sessions per week (14-day average)"),
        Field(name="sessions_per_day_14d", dtype=Float32,
              description="Sessions per day (14-day average)"),
        Field(name="avg_events_per_session_14d", dtype=Float32,
              description="Average events per session"),
        Field(name="content_completion_rate_7d", dtype=Float32,
              description="Fraction of started content completed (7-day)"),
        Field(name="hours_since_meaningful_action", dtype=Int32,
              description="Hours since last meaningful action"),
        Field(name="feature_adoption_breadth_14d", dtype=Float32,
              description="Breadth of feature usage (0-1 scale)"),
        Field(name="social_interactions_per_day_14d", dtype=Float32,
              description="Social interactions per day"),
        Field(name="session_consistency_cv", dtype=Float32,
              description="Coefficient of variation in session consistency"),
        Field(name="engagement_status", dtype=String,
              description="Status: active_today, active_this_week, dormant"),
        Field(name="total_events_14d", dtype=Int32,
              description="Total events in 14-day window"),
        Field(name="active_days_14d", dtype=Int32,
              description="Number of active days in 14-day window")
    ]
)


# ============================================================================
# FEATURE VIEWS: CHURN RISK
# ============================================================================

churn_features_view = FeatureView(
    name="churn_features",
    description="Predictive indicators of 30-day churn risk",
    entities=[user],
    ttl=timedelta(hours=24),
    online=True,
    offline=True,
    source=churn_features_snowflake,
    tags={"team": "retention", "domain": "churn_prediction"},
    features=[
        Field(name="session_decline_pct", dtype=Float32,
              description="Week-over-week % change in sessions"),
        Field(name="recency_score", dtype=Int32,
              description="Recency score (0-100, higher = more recent activity)"),
        Field(name="goal_progress_status", dtype=String,
              description="Goal progress: on_track, behind, stalled"),
        Field(name="notification_optout_rate", dtype=Float32,
              description="Fraction of notifications opted out")
    ]
)


# ============================================================================
# FEATURE VIEWS: RECOMMENDATIONS
# ============================================================================

recommendation_features_view = FeatureView(
    name="recommendation_features",
    description="Features for personalized content recommendations",
    entities=[user],
    ttl=timedelta(hours=24),
    online=True,
    offline=True,
    source=recommendation_features_snowflake,
    tags={"team": "personalization", "domain": "recommendations"},
    features=[
        Field(name="pref_beginner_content", dtype=Float32,
              description="Preference for beginner difficulty content (0-1)"),
        Field(name="pref_intermediate_content", dtype=Float32,
              description="Preference for intermediate difficulty content"),
        Field(name="activity_morning_pct", dtype=Float32,
              description="% of activity in morning (6-9am)"),
        Field(name="activity_lunch_pct", dtype=Float32,
              description="% of activity at lunch (12-3pm)"),
        Field(name="activity_evening_pct", dtype=Float32,
              description="% of activity in evening (6-9pm)"),
        Field(name="unique_content_items_14d", dtype=Int32,
              description="Number of unique content items consumed"),
        Field(name="has_liked", dtype=Bool,
              description="Whether user has liked content"),
        Field(name="has_shared", dtype=Bool,
              description="Whether user has shared content"),
        Field(name="has_commented", dtype=Bool,
              description="Whether user has commented")
    ]
)


# ============================================================================
# FEATURE VIEWS: USER PROFILE
# ============================================================================

user_profile_view = FeatureView(
    name="user_profile",
    description="User profile attributes and metadata",
    entities=[user],
    ttl=timedelta(days=30),  # Refresh monthly
    online=True,
    offline=True,
    source=user_profile_snowflake,
    tags={"team": "growth", "domain": "user_profiles"},
    features=[
        Field(name="email", dtype=String,
              description="User email address"),
        Field(name="lifecycle_stage", dtype=String,
              description="Lifecycle stage: new, activated, engaged, at_risk, dormant"),
        Field(name="signup_date", dtype=String,
              description="User signup date (ISO format)"),
        Field(name="primary_goal", dtype=String,
              description="User's stated primary goal"),
        Field(name="premium_tier", dtype=Bool,
              description="Whether user is premium subscriber"),
        Field(name="days_active", dtype=Int32,
              description="Days since signup")
    ]
)


# ============================================================================
# FEATURE SERVICES (MODELS)
# ============================================================================

# For engagement scoring model
engagement_score_features = FeatureService(
    name="engagement_score",
    description="Features for computing engagement score",
    features=[
        engagement_features_view[["sessions_per_week_14d",
                                 "content_completion_rate_7d",
                                 "feature_adoption_breadth_14d",
                                 "hours_since_meaningful_action",
                                 "social_interactions_per_day_14d"]],
        churn_features_view[["session_decline_pct", "recency_score"]]
    ]
)

# For churn prediction model
churn_prediction_features = FeatureService(
    name="churn_prediction",
    description="Features for predicting 30-day churn",
    features=[
        engagement_features_view[["sessions_per_week_14d",
                                 "hours_since_meaningful_action",
                                 "feature_adoption_breadth_14d",
                                 "active_days_14d"]],
        churn_features_view[["session_decline_pct",
                            "recency_score",
                            "goal_progress_status",
                            "notification_optout_rate"]],
        user_profile_view[["days_active", "lifecycle_stage"]]
    ]
)

# For personalization / recommendations
personalization_features = FeatureService(
    name="personalization",
    description="Features for personalized content recommendations",
    features=[
        user_profile_view[["primary_goal", "days_active"]],
        recommendation_features_view[["pref_beginner_content",
                                      "pref_intermediate_content",
                                      "activity_morning_pct",
                                      "activity_evening_pct",
                                      "unique_content_items_14d",
                                      "has_liked",
                                      "has_shared"]],
        engagement_features_view[["engagement_status", "feature_adoption_breadth_14d"]]
    ]
)


# ============================================================================
# FEATURE STORE CONFIGURATION
# ============================================================================

"""
Production deployment configuration:

    [project]
    project_name = "engagement-personalization"
    registry = "s3://my-bucket/feast/registry.db"

    [offline_store]
    type = "snowflake"
    database = "analytics"
    schema = "features"
    warehouse = "feature_compute_wh"

    [online_store]
    type = "redis"
    host = "redis-prod.engagement.svc.cluster.local"
    port = 6379
    db = 0
    ttl = 86400  # 24 hours

    [entity_keyway]
    key_extractor = "feast.infra.key_extractor.get_online_features"

    [flags]
    alpha_metadata_server = true


Materialization schedule:
    - Every 6 hours: Sync engagement_features to Redis (high-frequency)
    - Every 24 hours: Sync churn_features (daily refresh adequate)
    - Every 7 days: Sync user_profile (changes infrequently)

Cost estimate (AWS/GCP/Snowflake):
    - Snowflake compute: $50/day (feature computation)
    - Redis online store: $200/month (managed Redis)
    - S3 registry: $1/month
    - Total: ~$2,500/month at scale
"""


# ============================================================================
# UTILITY FUNCTIONS FOR MODEL SERVING
# ============================================================================

def get_feature_store() -> FeatureStore:
    """Initialize and return Feast FeatureStore."""
    return FeatureStore(repo_path=".")


def get_user_features_for_scoring(user_id: str, feature_store: FeatureStore) -> dict:
    """
    Fetch features for a single user for real-time scoring.

    Args:
        user_id: User ID
        feature_store: Feast FeatureStore instance

    Returns:
        Dict of feature name → value for model input
    """
    features = feature_store.get_online_features(
        features=[
            "engagement_score:sessions_per_week_14d",
            "engagement_score:content_completion_rate_7d",
            "engagement_score:feature_adoption_breadth_14d",
            "engagement_score:hours_since_meaningful_action",
            "churn_prediction:session_decline_pct",
            "churn_prediction:recency_score",
            "user_profile:lifecycle_stage"
        ],
        entity_rows=[{"user_id": user_id}]
    )
    return features.to_dict()


def get_batch_features_for_training(start_date: str, end_date: str,
                                     feature_store: FeatureStore) -> object:
    """
    Fetch batch features for model training.

    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        feature_store: Feast FeatureStore instance

    Returns:
        Pandas DataFrame with features for all users in date range
    """
    features = feature_store.get_historical_features(
        entity_df="SELECT DISTINCT user_id FROM segment.users",
        features=[
            "engagement_features:sessions_per_week_14d",
            "engagement_features:hours_since_meaningful_action",
            "churn_features:session_decline_pct",
            "churn_features:recency_score",
            "recommendation_features:pref_beginner_content",
            "user_profile:days_active"
        ],
        event_timestamp_column="date"
    )
    return features.to_pandas()


# ============================================================================
# MONITORING & DATA QUALITY
# ============================================================================

"""
Data quality checks built into Feast:

    - Null value checks: Flag if >5% nulls in any feature
    - Statistical drift: Compare distribution to baseline
    - Cardinality checks: Monitor for unexpected value explosion
    - Schema validation: Ensure types remain consistent

Example alert thresholds:
    - sessions_per_week_14d: expect 0-10 (alert if >15)
    - hours_since_meaningful_action: expect 0-336 (alert if >500)
    - engagement_status: expect 4 unique values (alert if >10)

Monitoring dashboards in Grafana show:
    - Feature availability (% non-null per feature)
    - Update latency (max staleness in online store)
    - Request latency (p50, p95, p99 for get_online_features)
    - Cache hit rate (Redis/online store efficiency)
"""
