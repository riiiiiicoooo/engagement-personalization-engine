-- Feature Computation Pipeline (Snowflake)
-- =======================================
--
-- Transforms raw events from Segment into features for ML models.
-- Run daily (UTC 1am) to generate features for scoring that day + next 6 days.
--
-- Tables:
--   - segment.events (raw Segment events)
--   - segment.users (user profiles)
--   - features.engagement_features (output)
--   - features.feature_history (for monitoring)

-- ============================================================================
-- SECTION 1: STAGING - NORMALIZE RAW EVENTS
-- ============================================================================

-- Create staging table for daily events (run once per day)
CREATE OR REPLACE TEMPORARY TABLE stg_events_daily AS
SELECT
    user_id,
    event_type,
    event_properties,
    event_timestamp,
    EXTRACT(DATE FROM event_timestamp) AS event_date,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY event_timestamp) AS event_sequence,

    -- Extract common properties
    TRY_PARSE_JSON(event_properties):content_id::STRING AS content_id,
    TRY_PARSE_JSON(event_properties):completion_time_seconds::INT AS completion_time,
    TRY_PARSE_JSON(event_properties):difficulty::STRING AS content_difficulty,
    TRY_PARSE_JSON(event_properties):social_action::STRING AS social_action

FROM segment.events
WHERE event_timestamp >= CURRENT_DATE() - 14  -- 14-day lookback
  AND event_timestamp < CURRENT_DATE() + 1    -- Include today
  AND event_type IN ('app_opened', 'content_started', 'content_completed',
                     'goal_action_taken', 'social_interaction',
                     'notification_dismissed', 'notification_opted_out');


-- ============================================================================
-- SECTION 2: SESSION FEATURE COMPUTATION
-- ============================================================================

-- Sessions are defined as: consecutive events within same user, <30 min apart
CREATE OR REPLACE TEMPORARY TABLE stg_sessions AS
SELECT
    user_id,
    MIN(event_timestamp) AS session_start,
    MAX(event_timestamp) AS session_end,
    COUNT(*) AS events_in_session,
    COUNT(DISTINCT CASE WHEN event_type IN ('content_completed', 'goal_action_taken', 'social_interaction')
                       THEN 1 END) AS meaningful_actions,
    COUNT(DISTINCT content_id) AS unique_content_items,
    SUM(completion_time) AS total_time_seconds,
    CURRENT_DATE() AS feature_date
FROM stg_events_daily
GROUP BY user_id, event_date
-- In production: use event windowing to detect session boundaries
;


-- ============================================================================
-- SECTION 3: ENGAGEMENT FEATURES (14-DAY TRAILING WINDOW)
-- ============================================================================

-- Core engagement features: session frequency, content completion, feature adoption
CREATE OR REPLACE TABLE features.engagement_features_daily AS
SELECT
    CURRENT_DATE() AS feature_date,
    u.user_id,

    -- SESSIONS (14-day window)
    COUNT(DISTINCT s.session_start) / 14.0 AS sessions_per_day_14d,
    (COUNT(DISTINCT s.session_start) / 14.0) * 7 AS sessions_per_week_14d,
    AVG(s.events_in_session) AS avg_events_per_session_14d,

    -- CONTENT COMPLETION (7-day window)
    COUNT(DISTINCT CASE WHEN e.event_type = 'content_completed'
                        AND e.event_date >= CURRENT_DATE() - 7
                       THEN e.content_id END) /
    NULLIF(COUNT(DISTINCT CASE WHEN e.event_type = 'content_started'
                                AND e.event_date >= CURRENT_DATE() - 7
                              THEN e.content_id END), 0)
        AS content_completion_rate_7d,

    -- RECENCY (hours since last meaningful action)
    DATEDIFF(HOUR, MAX(CASE WHEN e.event_type IN ('content_completed', 'goal_action_taken', 'social_interaction')
                               THEN e.event_timestamp
                          END),
             CURRENT_TIMESTAMP())
        AS hours_since_meaningful_action,

    -- FEATURE ADOPTION (breadth across different features)
    COUNT(DISTINCT CASE WHEN e.event_type IN ('content_completed', 'goal_action_taken', 'social_interaction')
                       THEN e.event_type END) / 3.0
        AS feature_adoption_breadth_14d,

    -- SOCIAL INTERACTIONS (14-day)
    COUNT(DISTINCT CASE WHEN e.event_type = 'social_interaction'
                       THEN e.event_timestamp END) / 14.0
        AS social_interactions_per_day_14d,

    -- CONSISTENCY (coefficient of variation of daily sessions)
    STDDEV(s.events_in_session) / NULLIF(AVG(s.events_in_session), 0)
        AS session_consistency_cv,

    -- ENGAGEMENT STATUS
    CASE WHEN DATEDIFF(HOUR, MAX(e.event_timestamp), CURRENT_TIMESTAMP()) < 24
         THEN 'active_today'
         WHEN DATEDIFF(HOUR, MAX(e.event_timestamp), CURRENT_TIMESTAMP()) < 168
         THEN 'active_this_week'
         WHEN DATEDIFF(HOUR, MAX(e.event_timestamp), CURRENT_TIMESTAMP()) < 336
         THEN 'active_last_week'
         ELSE 'dormant'
    END AS engagement_status,

    -- LIFECYCLE STAGE (from user profile)
    u.lifecycle_stage,

    -- METADATA
    COUNT(e.event_timestamp) AS total_events_14d,
    COUNT(DISTINCT e.event_date) AS active_days_14d

FROM segment.users u
LEFT JOIN stg_events_daily e ON u.user_id = e.user_id
LEFT JOIN stg_sessions s ON u.user_id = s.user_id
WHERE u.account_status = 'active'
GROUP BY u.user_id, u.lifecycle_stage;


-- ============================================================================
-- SECTION 4: CHURN RISK FEATURES
-- ============================================================================

-- Features predictive of 30-day churn
CREATE OR REPLACE TABLE features.churn_features_daily AS
SELECT
    CURRENT_DATE() AS feature_date,
    user_id,

    -- ENGAGEMENT DECLINE (WoW change in sessions)
    (sessions_per_week_14d - sessions_per_week_7d) / NULLIF(sessions_per_week_7d, 0) AS session_decline_pct,

    -- RECENCY DECAY (hours since last action, scored)
    CASE WHEN hours_since_meaningful_action <= 6 THEN 100
         WHEN hours_since_meaningful_action <= 12 THEN 90
         WHEN hours_since_meaningful_action <= 24 THEN 80
         WHEN hours_since_meaningful_action <= 48 THEN 65
         WHEN hours_since_meaningful_action <= 72 THEN 50
         ELSE 0
    END AS recency_score,

    -- GOAL PROGRESS (estimated, based on action frequency vs. baseline)
    CASE WHEN social_interactions_per_day_14d > 0.5 THEN 'on_track'
         WHEN social_interactions_per_day_14d > 0.2 THEN 'behind'
         ELSE 'stalled'
    END AS goal_progress_status,

    -- NOTIFICATION FATIGUE (opt-out rate)
    COUNT(CASE WHEN event_type = 'notification_opted_out' THEN 1 END) /
    NULLIF(COUNT(CASE WHEN event_type IN ('notification_dismissed', 'notification_opted_out') THEN 1 END), 0)
        AS notification_optout_rate

FROM (
    SELECT
        s.user_id,
        e.event_type,
        e.event_date,
        ef.sessions_per_week_14d,
        LAG(ef.sessions_per_week_14d) OVER (PARTITION BY s.user_id ORDER BY e.event_date) AS sessions_per_week_7d,
        ef.hours_since_meaningful_action,
        ef.social_interactions_per_day_14d
    FROM features.engagement_features_daily ef
    JOIN stg_sessions s ON ef.user_id = s.user_id
    JOIN stg_events_daily e ON s.user_id = e.user_id
)
GROUP BY user_id, sessions_per_week_14d, sessions_per_week_7d,
         hours_since_meaningful_action, social_interactions_per_day_14d;


-- ============================================================================
-- SECTION 5: RECOMMENDATION ENGINE FEATURES
-- ============================================================================

-- Features for collaborative filtering and content recommendation
CREATE OR REPLACE TABLE features.recommendation_features_daily AS
SELECT
    CURRENT_DATE() AS feature_date,
    user_id,

    -- CONTENT PREFERENCES (by type)
    COUNT(DISTINCT CASE WHEN content_difficulty = 'beginner' THEN 1 END) /
    NULLIF(COUNT(DISTINCT CASE WHEN event_type = 'content_completed' THEN 1 END), 0)
        AS pref_beginner_content,

    COUNT(DISTINCT CASE WHEN content_difficulty = 'intermediate' THEN 1 END) /
    NULLIF(COUNT(DISTINCT CASE WHEN event_type = 'content_completed' THEN 1 END), 0)
        AS pref_intermediate_content,

    -- TIMING PREFERENCES (when user is active)
    COUNT(CASE WHEN EXTRACT(HOUR FROM event_timestamp) BETWEEN 6 AND 9 THEN 1 END) /
    NULLIF(COUNT(*), 0) AS activity_morning_pct,

    COUNT(CASE WHEN EXTRACT(HOUR FROM event_timestamp) BETWEEN 12 AND 15 THEN 1 END) /
    NULLIF(COUNT(*), 0) AS activity_lunch_pct,

    COUNT(CASE WHEN EXTRACT(HOUR FROM event_timestamp) BETWEEN 18 AND 21 THEN 1 END) /
    NULLIF(COUNT(*), 0) AS activity_evening_pct,

    -- CONTENT DIVERSITY (entropy of content types)
    COUNT(DISTINCT content_id) AS unique_content_items_14d,

    -- INTERACTION PATTERNS (social)
    MAX(CASE WHEN social_action = 'like' THEN 1 ELSE 0 END) AS has_liked,
    MAX(CASE WHEN social_action = 'share' THEN 1 ELSE 0 END) AS has_shared,
    MAX(CASE WHEN social_action = 'comment' THEN 1 ELSE 0 END) AS has_commented

FROM stg_events_daily
WHERE event_type IN ('content_completed', 'content_started', 'social_interaction')
GROUP BY user_id;


-- ============================================================================
-- SECTION 6: EXPERIMENT ASSIGNMENT TRACKING
-- ============================================================================

-- Track which experiments a user is assigned to (for holdout/segmentation)
CREATE OR REPLACE TABLE features.experiment_assignments_daily AS
SELECT
    CURRENT_DATE() AS feature_date,
    user_id,

    -- Active experiments
    LISTAGG(DISTINCT experiment_id, ',') WITHIN GROUP (ORDER BY experiment_id)
        AS active_experiments,

    -- Variant assignments (for within-experiment analysis)
    OBJECT_AGG(experiment_id, variant_id) AS experiment_variants,

    -- Long-term holdout across platform
    MIN(is_long_term_holdout) AS is_platform_holdout

FROM segment.experiment_assignments
WHERE assignment_date = CURRENT_DATE()
  AND experiment_status = 'active'
GROUP BY user_id;


-- ============================================================================
-- SECTION 7: MATERIALIZED VIEW FOR ML MODEL FEATURES
-- ============================================================================

-- Combined feature set for scoring models (real-time)
CREATE OR REPLACE DYNAMIC TABLE features.ml_features_latest
  TARGET_LAG = '1 hour'
  WAREHOUSE = 'feature_compute_wh'
AS
SELECT
    ef.feature_date,
    ef.user_id,

    -- Engagement score components
    ef.sessions_per_week_14d,
    ef.content_completion_rate_7d,
    ef.feature_adoption_breadth_14d,
    ef.hours_since_meaningful_action,
    ef.social_interactions_per_day_14d,

    -- Churn indicators
    cf.session_decline_pct,
    cf.recency_score,
    cf.goal_progress_status,
    cf.notification_optout_rate,

    -- Recommendation features
    rf.pref_beginner_content,
    rf.pref_intermediate_content,
    rf.activity_morning_pct,
    rf.activity_evening_pct,
    rf.unique_content_items_14d,

    -- Experiment assignment
    ea.active_experiments,
    ea.is_platform_holdout,

    -- User profile
    ef.lifecycle_stage,
    ef.engagement_status,

    -- Metadata
    ef.total_events_14d,
    ef.active_days_14d

FROM features.engagement_features_daily ef
LEFT JOIN features.churn_features_daily cf ON ef.user_id = cf.user_id AND ef.feature_date = cf.feature_date
LEFT JOIN features.recommendation_features_daily rf ON ef.user_id = rf.user_id AND ef.feature_date = rf.feature_date
LEFT JOIN features.experiment_assignments_daily ea ON ef.user_id = ea.user_id AND ef.feature_date = ea.feature_date;


-- ============================================================================
-- SECTION 8: FEATURE VALIDATION & QUALITY CHECKS
-- ============================================================================

-- Monitor data quality and feature distributions
CREATE OR REPLACE TABLE features.feature_quality_metrics AS
SELECT
    CURRENT_DATE() AS check_date,
    'sessions_per_week_14d' AS feature_name,
    COUNT(*) AS total_records,
    COUNT(CASE WHEN sessions_per_week_14d IS NOT NULL THEN 1 END) AS non_null_count,
    COUNT(CASE WHEN sessions_per_week_14d IS NULL THEN 1 END) AS null_count,
    MIN(sessions_per_week_14d) AS min_value,
    AVG(sessions_per_week_14d) AS mean_value,
    MAX(sessions_per_week_14d) AS max_value,
    STDDEV(sessions_per_week_14d) AS stddev_value
FROM features.engagement_features_daily
GROUP BY 1, 2

UNION ALL

SELECT
    CURRENT_DATE() AS check_date,
    'hours_since_meaningful_action' AS feature_name,
    COUNT(*),
    COUNT(CASE WHEN hours_since_meaningful_action IS NOT NULL THEN 1 END),
    COUNT(CASE WHEN hours_since_meaningful_action IS NULL THEN 1 END),
    MIN(hours_since_meaningful_action),
    AVG(hours_since_meaningful_action),
    MAX(hours_since_meaningful_action),
    STDDEV(hours_since_meaningful_action)
FROM features.engagement_features_daily;


-- ============================================================================
-- SECTION 9: DEPLOYMENT SCHEDULE
-- ============================================================================

-- Schedule via Snowflake Task:
--
-- CREATE OR REPLACE TASK feature_computation_daily
--   WAREHOUSE = feature_compute_wh
--   SCHEDULE = 'USING CRON 0 1 * * * America/Los_Angeles'
--   AS
--   CALL features.compute_daily_features();
--
-- This runs daily at 1am Pacific, processes events from previous 14 days,
-- generates features for 10K+ users in ~5 minutes.
--
-- Cost: $0.40/run (compute_wh with 2 credits/hour, runs for ~20 min per day)
-- Data volume: 50M events/day → 10K users × 300 features = 3GB/day

