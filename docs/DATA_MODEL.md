# Data Model: Engagement & Personalization Engine

**Last Updated:** January 2025

---

## 1. Overview

The data model spans three storage layers, each optimized for its access pattern:

| Layer | Store | Purpose | Access Pattern |
|---|---|---|---|
| Operational | PostgreSQL | Experiment configs, flag definitions, segment rules, user profiles | Low-latency read/write, transactional consistency |
| Real-time | Redis | Engagement scores, flag values, experiment assignments, session state | Sub-millisecond reads, high throughput writes |
| Analytical | Snowflake | Event warehouse, behavioral aggregates, experiment analysis, ML training | Bulk reads, complex joins, historical queries |

---

## 2. Event Taxonomy

Every user interaction is captured as a structured event. Events are the raw material for engagement scoring, experiment analysis, and ML model training.

### 2.1 Event Schema

```json
{
  "event_id": "uuid",
  "event_type": "content_completed",
  "user_id": "uuid",
  "anonymous_id": "device-uuid",
  "timestamp": "2025-01-15T14:32:08.123Z",
  "session_id": "uuid",
  "platform": "ios",
  "app_version": "3.4.1",
  "properties": {
    "content_id": "article-892",
    "content_type": "guided_activity",
    "content_category": "stress_management",
    "duration_seconds": 342,
    "completion_pct": 100,
    "goal_cluster": "mental_wellness"
  },
  "context": {
    "engagement_score": 72,
    "engagement_tier": 2,
    "lifecycle_stage": "engaged",
    "experiments": [
      {"experiment_id": "exp-041", "variant": "treatment_a"}
    ],
    "flags": {
      "new_home_feed_v2": true,
      "progress_indicators": false
    }
  }
}
```

### 2.2 Event Catalog

**User Lifecycle Events:**

| Event | Trigger | Key Properties |
|---|---|---|
| `user_signed_up` | Registration complete | signup_source, referral_code, platform |
| `onboarding_completed` | Finished onboarding flow | goals_selected[], onboarding_duration_seconds |
| `first_key_action` | Completed first meaningful action | action_type, time_since_signup_hours |
| `subscription_started` | Paid subscription activated | plan_type, trial_used, price |
| `subscription_cancelled` | Subscription cancelled | cancellation_reason, lifetime_days |
| `account_deactivated` | User deactivated account | reason, lifetime_days |

**Engagement Events:**

| Event | Trigger | Key Properties |
|---|---|---|
| `app_opened` | App foreground | source (organic, push, email, deeplink) |
| `session_started` | New session detected | session_number, days_since_last_session |
| `session_ended` | App background > 30s | duration_seconds, actions_count, depth_score |
| `content_viewed` | Content item displayed | content_id, content_type, position_in_feed, source (feed, search, recommendation) |
| `content_started` | User began content | content_id, content_type |
| `content_completed` | User finished content | content_id, duration_seconds, completion_pct |
| `goal_action_taken` | Action tied to user's goal | goal_id, action_type, progress_pct |
| `streak_milestone` | Reached streak milestone | streak_days, milestone_type (7, 14, 30, 60, 90) |

**Notification Events:**

| Event | Trigger | Key Properties |
|---|---|---|
| `notification_sent` | Notification dispatched | channel (push, email, in_app), template_id, notification_type |
| `notification_received` | Confirmed delivery | channel, latency_ms |
| `notification_opened` | User tapped/opened | channel, time_to_open_seconds |
| `notification_dismissed` | User dismissed | channel |
| `notification_opt_out` | User disabled channel | channel, previous_preference |

**Experiment Events:**

| Event | Trigger | Key Properties |
|---|---|---|
| `experiment_assigned` | User assigned to experiment | experiment_id, variant, assignment_method |
| `experiment_exposed` | User saw experiment variant | experiment_id, variant, surface, timestamp |
| `flag_evaluated` | Feature flag checked | flag_key, value_returned, rule_matched |

**Score Events:**

| Event | Trigger | Key Properties |
|---|---|---|
| `engagement_score_updated` | Score recalculated | new_score, previous_score, delta, components{} |
| `tier_changed` | User moved between tiers | old_tier, new_tier, trigger_event |
| `segment_transition` | User entered/exited segment | segment_id, direction (entered/exited), trigger |
| `intervention_triggered` | At-risk user flagged | intervention_type, churn_probability, trigger_rule |
| `intervention_outcome` | Intervention result measured | intervention_id, outcome (re-engaged, no_response, opted_out) |

---

## 3. PostgreSQL Schema (Operational)

### 3.1 Users and Profiles

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    signup_source VARCHAR(50),             -- organic, referral, paid, etc.
    platform VARCHAR(20),                  -- ios, android, web
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE user_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    goals JSONB DEFAULT '[]',              -- Selected during onboarding
    goal_cluster VARCHAR(50),              -- ML-assigned cluster (A-E)
    onboarding_completed_at TIMESTAMPTZ,
    subscription_status VARCHAR(20) DEFAULT 'free',
    subscription_started_at TIMESTAMPTZ,
    notification_preferences JSONB DEFAULT '{
        "push_enabled": true,
        "email_enabled": true,
        "in_app_enabled": true,
        "quiet_hours_start": null,
        "quiet_hours_end": null
    }',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_last_active ON users(last_active_at);
CREATE INDEX idx_users_created ON users(created_at);
CREATE INDEX idx_profiles_goal_cluster ON user_profiles(goal_cluster);
CREATE INDEX idx_profiles_subscription ON user_profiles(subscription_status);
```

### 3.2 Experiments

```sql
CREATE TABLE experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    hypothesis TEXT NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
        -- draft, review, active, paused, stopped, completed
    
    -- Targeting
    target_segment JSONB,                  -- Segment rules for eligibility
    mutual_exclusion_group VARCHAR(100),   -- Prevents conflicting experiments
    
    -- Variants
    variants JSONB NOT NULL,
    -- [
    --   {"id": "control", "name": "Control", "weight": 50},
    --   {"id": "treatment_a", "name": "Progress Indicators", "weight": 50}
    -- ]
    
    -- Metrics
    primary_metric VARCHAR(100) NOT NULL,  -- e.g., "retention_7d"
    guardrail_metrics JSONB DEFAULT '[]',
    -- [
    --   {"metric": "session_duration", "direction": "must_not_decrease", "threshold": -0.10}
    -- ]
    
    -- Rollout
    rollout_percentage INTEGER DEFAULT 100,  -- Within eligible segment
    
    -- Statistical design
    minimum_detectable_effect FLOAT,       -- e.g., 0.05 for 5% lift
    required_sample_per_arm INTEGER,
    confidence_level FLOAT DEFAULT 0.95,
    
    -- Auto-stop
    auto_stop_enabled BOOLEAN DEFAULT true,
    
    -- Holdout
    long_term_holdout_pct INTEGER DEFAULT 5,
    
    -- Metadata
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    decision VARCHAR(20),                  -- ship, iterate, kill
    decision_rationale TEXT,
    
    CONSTRAINT valid_status CHECK (
        status IN ('draft', 'review', 'active', 'paused', 'stopped', 'completed')
    )
);

CREATE TABLE experiment_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES experiments(id),
    user_id UUID NOT NULL REFERENCES users(id),
    variant_id VARCHAR(50) NOT NULL,
    bucket INTEGER NOT NULL,               -- hash result (0-99)
    is_holdout BOOLEAN DEFAULT false,      -- In long-term holdout group
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(experiment_id, user_id)
);

CREATE TABLE experiment_exposures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES experiments(id),
    user_id UUID NOT NULL REFERENCES users(id),
    variant_id VARCHAR(50) NOT NULL,
    surface VARCHAR(100),                  -- Where exposure happened (home_feed, settings, etc.)
    exposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for experiment analysis queries
CREATE INDEX idx_assignments_experiment ON experiment_assignments(experiment_id);
CREATE INDEX idx_assignments_user ON experiment_assignments(user_id);
CREATE INDEX idx_exposures_experiment ON experiment_exposures(experiment_id);
CREATE INDEX idx_exposures_experiment_variant ON experiment_exposures(experiment_id, variant_id);
CREATE INDEX idx_exposures_timestamp ON experiment_exposures(exposed_at);

-- Partitioned by month for query performance on large exposure tables
-- In production: experiment_exposures is partitioned by exposed_at month
```

### 3.3 Feature Flags

```sql
CREATE TABLE feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_key VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    flag_type VARCHAR(20) NOT NULL DEFAULT 'boolean',
        -- boolean, string, integer, json
    default_value JSONB NOT NULL DEFAULT 'false',
    
    -- State
    is_active BOOLEAN DEFAULT true,
    is_killed BOOLEAN DEFAULT false,       -- Kill switch
    
    -- Rollout
    rollout_percentage INTEGER DEFAULT 0,  -- 0-100
    
    -- Targeting
    target_segments JSONB DEFAULT '[]',    -- Segment IDs to target
    allowlist JSONB DEFAULT '[]',          -- User IDs always ON
    blocklist JSONB DEFAULT '[]',          -- User IDs always OFF
    
    -- Variants (for multivariate flags)
    variants JSONB,
    -- [
    --   {"id": "v1", "value": "blue_button", "weight": 50},
    --   {"id": "v2", "value": "green_button", "weight": 50}
    -- ]
    
    -- Lifecycle
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stale_alert_at TIMESTAMPTZ,            -- Alert if unchanged for 30 days
    archived_at TIMESTAMPTZ,
    
    -- Dependencies
    depends_on JSONB DEFAULT '[]',         -- Flag keys this flag requires
    
    -- Linked experiment (if flag gates an experiment)
    experiment_id UUID REFERENCES experiments(id)
);

CREATE TABLE flag_evaluation_log (
    id BIGSERIAL PRIMARY KEY,
    flag_key VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL,
    value_returned JSONB NOT NULL,
    rule_matched VARCHAR(50),              -- kill_switch, allowlist, segment, rollout, default
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_flags_key ON feature_flags(flag_key);
CREATE INDEX idx_flags_active ON feature_flags(is_active) WHERE is_active = true;
CREATE INDEX idx_flag_log_flag ON flag_evaluation_log(flag_key, evaluated_at);

-- Partition evaluation log by day (high volume)
-- In production: flag_evaluation_log partitioned by evaluated_at day
```

### 3.4 Segments

```sql
CREATE TABLE segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    segment_type VARCHAR(30) NOT NULL,
        -- lifecycle_stage, behavioral_cohort, engagement_tier, goal_cluster, custom
    
    -- Rules (evaluated against user context)
    rules JSONB NOT NULL,
    -- Example for custom segment "high-value at-risk":
    -- {
    --   "operator": "AND",
    --   "conditions": [
    --     {"field": "engagement_tier", "op": "in", "value": [3, 4]},
    --     {"field": "subscription_status", "op": "eq", "value": "active"},
    --     {"field": "engagement_score_delta_7d", "op": "lt", "value": -15}
    --   ]
    -- }
    
    -- Compute
    is_realtime BOOLEAN DEFAULT false,     -- Evaluated on every request (vs. batch)
    refresh_interval_minutes INTEGER,      -- For batch segments
    
    -- Metadata
    estimated_size INTEGER,                -- Approximate user count
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_segment_membership (
    user_id UUID NOT NULL REFERENCES users(id),
    segment_id UUID NOT NULL REFERENCES segments(id),
    entered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exited_at TIMESTAMPTZ,                 -- NULL if currently in segment
    
    PRIMARY KEY (user_id, segment_id, entered_at)
);

-- Indexes
CREATE INDEX idx_membership_user ON user_segment_membership(user_id) 
    WHERE exited_at IS NULL;
CREATE INDEX idx_membership_segment ON user_segment_membership(segment_id) 
    WHERE exited_at IS NULL;
CREATE INDEX idx_membership_segment_dates ON user_segment_membership(segment_id, entered_at, exited_at);
```

### 3.5 Interventions

```sql
CREATE TABLE interventions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    
    -- Trigger
    trigger_type VARCHAR(50) NOT NULL,     -- score_drop, tier_change, churn_prediction, scheduled
    trigger_data JSONB,                    -- Score values, prediction probability, etc.
    churn_probability FLOAT,
    
    -- Execution
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
        -- pending, active, completed, expired, suppressed
    intervention_plan JSONB NOT NULL,
    -- {
    --   "steps": [
    --     {"day": 1, "channel": "in_app", "template": "gentle_nudge", "sent": false},
    --     {"day": 3, "channel": "push", "template": "streak_risk", "sent": false},
    --     {"day": 7, "channel": "email", "template": "content_digest", "sent": false}
    --   ]
    -- }
    current_step INTEGER DEFAULT 0,
    
    -- Outcome
    outcome VARCHAR(30),                   -- re_engaged, no_response, opted_out
    outcome_measured_at TIMESTAMPTZ,
    re_engagement_event_id UUID,
    
    -- Metadata
    experiment_id UUID REFERENCES experiments(id),  -- If intervention is being tested
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_interventions_user ON interventions(user_id);
CREATE INDEX idx_interventions_status ON interventions(status) WHERE status = 'active';
CREATE INDEX idx_interventions_outcome ON interventions(outcome);
```

---

## 4. Redis Schema (Real-Time)

### 4.1 Key Structure

```
# Engagement scores (updated on every meaningful event)
engagement:{user_id}
├── score: 72                          (integer, 0-100)
├── tier: 2                            (integer, 1-5)
├── recency: 85                        (component score)
├── frequency: 68                      (component score)
├── depth: 72                          (component score)
├── consistency: 60                    (component score)
├── progression: 55                    (component score)
├── updated_at: 1705312328             (unix timestamp)
└── TTL: 86400 (24 hours)

# Feature flag configs (refreshed on update, TTL 5 min)
flag:{flag_key}
├── type: "boolean"
├── default: false
├── killed: false
├── rollout_pct: 25
├── allowlist: ["user-1", "user-2"]
├── blocklist: []
├── target_segments: ["segment-abc"]
├── variants: [...]
└── TTL: 300 (5 minutes)

# Experiment assignments (persisted for experiment duration)
exp_assign:{user_id}:{experiment_id}
├── variant: "treatment_a"
├── bucket: 37
├── is_holdout: false
├── assigned_at: 1705312328
└── TTL: experiment duration + 30 days

# User segment memberships (refreshed hourly for batch, on-event for realtime)
segments:{user_id}
├── lifecycle_stage: "engaged"
├── behavioral_cohort: "regular"
├── engagement_tier: 2
├── goal_cluster: "mental_wellness"
├── custom_segments: ["high-value", "ios-power-users"]
└── TTL: 3600 (1 hour)

# Session tracking
session:{user_id}
├── session_id: "uuid"
├── started_at: 1705312328
├── events_count: 7
├── meaningful_actions: 3
└── TTL: 1800 (30 minutes, extends on activity)

# Notification tracking (weekly rolling window)
notif_count:{user_id}:{week}
├── sent: 3
├── opened: 2
├── dismissed: 1
└── TTL: 604800 (7 days)
```

### 4.2 Pub/Sub Channels

```
# Flag update notification (instant cache invalidation)
Channel: flag_updates
Message: {"flag_key": "new_home_feed_v2", "action": "updated"}
→ All API servers invalidate local cache for this flag

# Experiment state changes
Channel: experiment_updates
Message: {"experiment_id": "exp-041", "action": "stopped", "reason": "guardrail_breach"}
→ All API servers stop assigning users to this experiment

# Score alerts (for intervention system)
Channel: score_alerts
Message: {"user_id": "abc-123", "alert_type": "rapid_decline", "score": 38, "delta_3d": -22}
→ Intervention service evaluates and may trigger intervention
```

---

## 5. Snowflake Schema (Analytical)

### 5.1 Raw Events

```sql
-- Raw events from Segment (append-only, partitioned by date)
CREATE TABLE raw_events (
    event_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    user_id VARCHAR,
    anonymous_id VARCHAR,
    timestamp TIMESTAMP_NTZ NOT NULL,
    session_id VARCHAR,
    platform VARCHAR,
    app_version VARCHAR,
    properties VARIANT,                    -- Flexible JSON
    context VARIANT,                       -- Engagement score, experiments, flags at time of event
    received_at TIMESTAMP_NTZ,
    loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY (TO_DATE(timestamp), event_type);
```

### 5.2 dbt Models (Transformed)

```sql
-- User behavioral profile (rebuilt daily by dbt)
-- This is the core table for experiment analysis and ML training
CREATE TABLE user_behavioral_profiles AS
SELECT
    user_id,
    
    -- Engagement (trailing 14 days)
    COUNT(DISTINCT CASE WHEN event_type IN ('content_completed', 'goal_action_taken') 
        AND timestamp > DATEADD(day, -14, CURRENT_DATE) THEN DATE(timestamp) END) 
        AS active_days_14d,
    COUNT(DISTINCT CASE WHEN timestamp > DATEADD(day, -14, CURRENT_DATE) 
        THEN session_id END) 
        AS sessions_14d,
    AVG(CASE WHEN event_type = 'session_ended' 
        AND timestamp > DATEADD(day, -14, CURRENT_DATE) 
        THEN properties:duration_seconds::INT END) 
        AS avg_session_duration_14d,
    
    -- Content engagement (trailing 7 days)
    COUNT(CASE WHEN event_type = 'content_completed' 
        AND timestamp > DATEADD(day, -7, CURRENT_DATE) THEN 1 END) 
        AS content_completions_7d,
    COUNT(CASE WHEN event_type = 'content_viewed' 
        AND timestamp > DATEADD(day, -7, CURRENT_DATE) THEN 1 END) 
        AS content_views_7d,
    
    -- Notification engagement (trailing 7 days)
    COUNT(CASE WHEN event_type = 'notification_opened' 
        AND timestamp > DATEADD(day, -7, CURRENT_DATE) THEN 1 END) 
        AS notification_opens_7d,
    COUNT(CASE WHEN event_type = 'notification_dismissed' 
        AND timestamp > DATEADD(day, -7, CURRENT_DATE) THEN 1 END) 
        AS notification_dismissals_7d,
    
    -- Recency
    DATEDIFF(hour, MAX(CASE WHEN event_type IN ('content_completed', 'goal_action_taken') 
        THEN timestamp END), CURRENT_TIMESTAMP()) 
        AS hours_since_last_meaningful_action,
    
    -- Lifecycle
    DATEDIFF(day, MIN(CASE WHEN event_type = 'user_signed_up' 
        THEN timestamp END), CURRENT_DATE) 
        AS days_since_signup,
    
    -- Goal progress
    MAX(CASE WHEN event_type = 'goal_action_taken' 
        THEN properties:progress_pct::FLOAT END) 
        AS goal_progress_pct,
    
    -- Snapshot date
    CURRENT_DATE AS profile_date
    
FROM raw_events
WHERE user_id IS NOT NULL
GROUP BY user_id;


-- Experiment results table (rebuilt on demand for active experiments)
CREATE TABLE experiment_results AS
SELECT
    e.experiment_id,
    e.variant_id,
    
    -- Sample
    COUNT(DISTINCT e.user_id) AS users_assigned,
    COUNT(DISTINCT exp.user_id) AS users_exposed,
    
    -- Primary metric example: 7-day retention
    COUNT(DISTINCT CASE WHEN ret.returned_within_7d THEN e.user_id END) 
        AS retained_7d,
    COUNT(DISTINCT CASE WHEN ret.returned_within_7d THEN e.user_id END)::FLOAT 
        / NULLIF(COUNT(DISTINCT exp.user_id), 0) 
        AS retention_rate_7d,
    
    -- Guardrail: session duration
    AVG(s.avg_session_duration) AS avg_session_duration,
    
    -- Guardrail: crash rate
    SUM(s.crash_count)::FLOAT / NULLIF(SUM(s.session_count), 0) AS crash_rate

FROM experiment_assignments e
LEFT JOIN experiment_exposures exp 
    ON e.experiment_id = exp.experiment_id AND e.user_id = exp.user_id
LEFT JOIN user_retention_7d ret 
    ON e.user_id = ret.user_id AND ret.cohort_date = DATE(e.assigned_at)
LEFT JOIN user_session_metrics s 
    ON e.user_id = s.user_id 
    AND s.period_start >= DATE(e.assigned_at)
    AND s.period_start < DATEADD(day, 14, DATE(e.assigned_at))
GROUP BY e.experiment_id, e.variant_id;


-- Cohort retention table (rebuilt daily)
CREATE TABLE cohort_retention AS
SELECT
    DATE(u.created_at) AS signup_date,
    u.signup_source,
    up.goal_cluster,
    
    COUNT(DISTINCT u.id) AS cohort_size,
    
    COUNT(DISTINCT CASE WHEN EXISTS (
        SELECT 1 FROM raw_events e 
        WHERE e.user_id = u.id 
        AND e.event_type IN ('content_completed', 'goal_action_taken')
        AND e.timestamp BETWEEN u.created_at + INTERVAL '1 day' 
            AND u.created_at + INTERVAL '7 days'
    ) THEN u.id END) AS retained_day_7,
    
    COUNT(DISTINCT CASE WHEN EXISTS (
        SELECT 1 FROM raw_events e 
        WHERE e.user_id = u.id 
        AND e.event_type IN ('content_completed', 'goal_action_taken')
        AND e.timestamp BETWEEN u.created_at + INTERVAL '24 days' 
            AND u.created_at + INTERVAL '30 days'
    ) THEN u.id END) AS retained_day_30,
    
    COUNT(DISTINCT CASE WHEN EXISTS (
        SELECT 1 FROM raw_events e 
        WHERE e.user_id = u.id 
        AND e.event_type IN ('content_completed', 'goal_action_taken')
        AND e.timestamp BETWEEN u.created_at + INTERVAL '83 days' 
            AND u.created_at + INTERVAL '90 days'
    ) THEN u.id END) AS retained_day_90

FROM users u
JOIN user_profiles up ON u.id = up.user_id
GROUP BY DATE(u.created_at), u.signup_source, up.goal_cluster;
```

### 5.3 Feature Store Tables (Feast)

```sql
-- Features for churn prediction model (daily refresh)
CREATE TABLE feature_store_churn_features AS
SELECT
    user_id,
    CURRENT_DATE AS feature_date,
    
    -- Engagement features
    active_days_14d,
    sessions_14d,
    avg_session_duration_14d,
    content_completions_7d,
    hours_since_last_meaningful_action,
    
    -- Trend features (this week vs. last week)
    sessions_7d - sessions_prev_7d AS session_delta_wow,
    completions_7d - completions_prev_7d AS completion_delta_wow,
    
    -- Notification features
    notification_opens_7d,
    notification_dismissals_7d,
    CASE WHEN notification_sends_7d > 0 
        THEN notification_opens_7d::FLOAT / notification_sends_7d 
        ELSE 0 END AS notification_open_rate_7d,
    
    -- User features
    days_since_signup,
    goal_cluster,
    subscription_status,
    platform,
    
    -- Goal features
    goal_progress_pct,
    days_since_last_goal_action,
    
    -- Engagement score (from scoring engine)
    engagement_score,
    engagement_tier,
    score_delta_7d
    
FROM user_behavioral_profiles
JOIN user_profiles ON user_behavioral_profiles.user_id = user_profiles.user_id;

-- Point-in-time correct training labels
-- For each user on each day: did they churn within the next 14 days?
CREATE TABLE churn_labels AS
SELECT
    user_id,
    label_date,
    CASE WHEN next_activity_date IS NULL 
        OR DATEDIFF(day, label_date, next_activity_date) > 14 
        THEN 1 ELSE 0 END AS churned_14d
FROM user_activity_calendar;
```

---

## 6. Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────────────┐       ┌─────────────────┐
│ users         │       │ user_profiles         │       │ segments        │
│               │       │                       │       │                 │
│ id (PK)       │──1:1──│ user_id (PK, FK)     │       │ id (PK)         │
│ email         │       │ goals                 │       │ name            │
│ display_name  │       │ goal_cluster          │       │ segment_type    │
│ signup_source │       │ subscription_status   │       │ rules           │
│ platform      │       │ notification_prefs    │       │ is_realtime     │
│ timezone      │       │                       │       │                 │
│ created_at    │       └───────────────────────┘       └────────┬────────┘
│ last_active_at│                                                 │
│               │       ┌──────────────────────┐                  │
└───────┬───────┘       │ user_segment_         │                  │
        │               │ membership            │──────────────────┘
        │               │                       │
        ├───────────────│ user_id (FK)          │
        │               │ segment_id (FK)       │
        │               │ entered_at            │
        │               │ exited_at             │
        │               └───────────────────────┘
        │
        │               ┌──────────────────────┐
        │               │ experiments           │
        │               │                       │
        │               │ id (PK)               │
        │               │ name                  │
        │               │ hypothesis            │
        ├───────────────│ status                │
        │           │   │ variants              │
        │           │   │ primary_metric        │
        │           │   │ guardrail_metrics     │
        │           │   │ rollout_percentage    │
        │           │   │ owner_id (FK)         │
        │           │   └───────────┬───────────┘
        │           │               │
        │           │               │
        │    ┌──────┴───────┐  ┌───┴──────────────────┐
        │    │ experiment_   │  │ experiment_           │
        │    │ assignments   │  │ exposures             │
        │    │               │  │                       │
        ├────│ user_id (FK)  │  │ user_id (FK)          │
        │    │ experiment_id │  │ experiment_id (FK)     │
        │    │ variant_id    │  │ variant_id             │
        │    │ bucket        │  │ surface                │
        │    │ is_holdout    │  │ exposed_at             │
        │    └───────────────┘  └───────────────────────┘
        │
        │               ┌──────────────────────┐
        │               │ feature_flags         │
        │               │                       │
        │               │ id (PK)               │
        │               │ flag_key (UNIQUE)     │
        ├───────────────│ rollout_percentage    │
        │               │ target_segments       │
        │               │ is_killed             │
        │               │ experiment_id (FK)    │
        │               └───────────────────────┘
        │
        │               ┌──────────────────────┐
        │               │ interventions         │
        │               │                       │
        │               │ id (PK)               │
        └───────────────│ user_id (FK)          │
                        │ trigger_type          │
                        │ churn_probability     │
                        │ intervention_plan     │
                        │ status                │
                        │ outcome               │
                        └───────────────────────┘
```

---

## 7. Indexing Strategy

### 7.1 PostgreSQL Indexes

| Table | Index | Type | Purpose |
|---|---|---|---|
| users | `idx_users_last_active` | B-tree | Identify inactive users for intervention |
| users | `idx_users_created` | B-tree | Cohort analysis by signup date |
| user_profiles | `idx_profiles_goal_cluster` | B-tree | Segment users by goal type |
| experiments | `idx_experiments_status` | B-tree (partial: active) | Quickly find active experiments |
| experiment_assignments | `idx_assignments_experiment` | B-tree | Get all assignments for an experiment |
| experiment_assignments | `idx_assignments_user` | B-tree | Get all experiments a user is in |
| experiment_exposures | `idx_exposures_experiment_variant` | Composite B-tree | Experiment analysis queries |
| feature_flags | `idx_flags_key` | B-tree | Flag lookup by key |
| user_segment_membership | `idx_membership_user` | B-tree (partial: active) | Current segment membership |
| interventions | `idx_interventions_status` | B-tree (partial: active) | Find active interventions |

### 7.2 Snowflake Clustering

| Table | Cluster Key | Purpose |
|---|---|---|
| raw_events | `(TO_DATE(timestamp), event_type)` | Partition pruning for date-range + event-type queries |
| user_behavioral_profiles | `(profile_date)` | Efficient point-in-time queries for ML training |
| experiment_results | `(experiment_id)` | Fast experiment-level analysis |
| cohort_retention | `(signup_date, goal_cluster)` | Cohort analysis by date and segment |

---

## 8. Data Retention

| Data Type | Retention | Rationale |
|---|---|---|
| Raw events (Snowflake) | 2 years | Historical analysis, cohort studies, ML training |
| User behavioral profiles | 1 year (daily snapshots) | Trend analysis, model training windows |
| Experiment assignments/exposures | Experiment lifetime + 1 year | Long-term holdout analysis |
| Experiment configs + results | Indefinite | Institutional learning repository |
| Feature flag evaluation log | 90 days | Debugging and audit; high volume, limited long-term value |
| Engagement score history | 90 days (daily granularity) | Trend analysis for intervention tuning |
| Intervention records | 1 year | Effectiveness analysis |
| User PII | Account lifetime + 30 days post-deletion | CCPA/GDPR compliance |
| Redis caches | TTL-based (5 min to 24 hours) | Ephemeral by design |
