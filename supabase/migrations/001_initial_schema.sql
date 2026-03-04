-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email VARCHAR(255) NOT NULL UNIQUE,
  user_id TEXT NOT NULL UNIQUE,
  engagement_score NUMERIC(5,2) DEFAULT 50,
  lifecycle_stage VARCHAR(50) DEFAULT 'new', -- new, activated, engaged, at-risk, dormant, reactivated
  behavioral_cohort VARCHAR(50) DEFAULT 'casual', -- power_user, regular, casual, drifting, dormant, churned
  goal_cluster VARCHAR(50) DEFAULT 'general', -- weight_mgmt, fitness, mental_wellness, chronic_condition, general
  engagement_tier INT DEFAULT 3, -- 1-5
  churn_risk_score NUMERIC(5,2) DEFAULT 0,
  last_activity_at TIMESTAMP DEFAULT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_user_id ON users(user_id);
CREATE INDEX idx_users_lifecycle_stage ON users(lifecycle_stage);
CREATE INDEX idx_users_engagement_tier ON users(engagement_tier);

-- ============================================================================
-- EVENTS TABLE - User activity tracking
-- ============================================================================
CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event_type VARCHAR(100) NOT NULL,
  event_name VARCHAR(100) NOT NULL,
  properties JSONB DEFAULT '{}',
  session_id TEXT,
  timestamp TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_events_user_id ON events(user_id);
CREATE INDEX idx_events_event_type ON events(event_type);
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_user_id_timestamp ON events(user_id, timestamp);

-- ============================================================================
-- EXPERIMENTS TABLE - A/B tests configuration
-- ============================================================================
CREATE TABLE experiments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  experiment_id TEXT NOT NULL UNIQUE,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  status VARCHAR(50) DEFAULT 'draft', -- draft, running, paused, completed
  hypothesis TEXT,
  primary_metric VARCHAR(100),
  guardrail_metrics TEXT[] DEFAULT ARRAY[]::TEXT[],
  target_segment VARCHAR(100),
  config JSONB,
  start_date TIMESTAMP,
  end_date TIMESTAMP,
  created_by UUID,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_experiments_status ON experiments(status);
CREATE INDEX idx_experiments_start_date ON experiments(start_date);

-- ============================================================================
-- FEATURE FLAGS TABLE
-- ============================================================================
CREATE TABLE feature_flags (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  flag_id TEXT NOT NULL UNIQUE,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  status VARCHAR(50) DEFAULT 'off', -- off, on, rollout
  rollout_percentage INT DEFAULT 0,
  targeting_rules JSONB DEFAULT '{"segments": [], "user_ids": []}',
  default_value BOOLEAN DEFAULT FALSE,
  created_by UUID,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_feature_flags_flag_id ON feature_flags(flag_id);
CREATE INDEX idx_feature_flags_status ON feature_flags(status);

-- ============================================================================
-- NOTIFICATIONS TABLE - Notification send history and preferences
-- ============================================================================
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  notification_id TEXT NOT NULL UNIQUE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  notification_type VARCHAR(100),
  channel VARCHAR(50), -- email, push, in_app
  status VARCHAR(50) DEFAULT 'pending', -- pending, sent, failed, bounced, opened, clicked
  subject VARCHAR(255),
  message TEXT,
  template_id TEXT,
  template_vars JSONB DEFAULT '{}',
  sent_at TIMESTAMP,
  opened_at TIMESTAMP,
  clicked_at TIMESTAMP,
  failed_reason TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_sent_at ON notifications(sent_at);

-- ============================================================================
-- NOTIFICATION PREFERENCES TABLE
-- ============================================================================
CREATE TABLE notification_preferences (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
  notification_frequency VARCHAR(50) DEFAULT 'daily', -- never, weekly, 3x_week, daily, real_time
  preferred_send_time TIME DEFAULT '09:00',
  timezone VARCHAR(50) DEFAULT 'UTC',
  enabled_channels TEXT[] DEFAULT ARRAY['email'],
  do_not_disturb_start TIME,
  do_not_disturb_end TIME,
  disable_all BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notification_preferences_user_id ON notification_preferences(user_id);

-- ============================================================================
-- CONTENT RECOMMENDATIONS TABLE
-- ============================================================================
CREATE TABLE recommendations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  recommendation_id TEXT NOT NULL UNIQUE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content_id TEXT NOT NULL,
  content_type VARCHAR(100), -- article, program, activity, challenge
  content_title VARCHAR(255),
  rank INT,
  score NUMERIC(5,3),
  reason VARCHAR(255), -- collaborative_filtering, content_affinity, trending
  experiment_id UUID REFERENCES experiments(id),
  variant VARCHAR(100),
  clicked BOOLEAN DEFAULT FALSE,
  completed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP
);

CREATE INDEX idx_recommendations_user_id ON recommendations(user_id);
CREATE INDEX idx_recommendations_user_id_created_at ON recommendations(user_id, created_at);
CREATE INDEX idx_recommendations_content_id ON recommendations(content_id);

-- ============================================================================
-- COHORT ASSIGNMENTS - Track user segment membership and changes
-- ============================================================================
CREATE TABLE cohort_assignments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  lifecycle_stage VARCHAR(50),
  behavioral_cohort VARCHAR(50),
  goal_cluster VARCHAR(50),
  engagement_tier INT,
  previous_tier INT,
  tier_changed BOOLEAN DEFAULT FALSE,
  assigned_at TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cohort_assignments_user_id ON cohort_assignments(user_id);
CREATE INDEX idx_cohort_assignments_lifecycle_stage ON cohort_assignments(lifecycle_stage);
CREATE INDEX idx_cohort_assignments_engagement_tier ON cohort_assignments(engagement_tier);

-- ============================================================================
-- EXPERIMENT ASSIGNMENTS - Track which users are in which experiment variants
-- ============================================================================
CREATE TABLE experiment_assignments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  variant VARCHAR(100),
  assigned_at TIMESTAMP DEFAULT NOW(),
  exposed BOOLEAN DEFAULT FALSE,
  exposed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, experiment_id)
);

CREATE INDEX idx_experiment_assignments_user_id ON experiment_assignments(user_id);
CREATE INDEX idx_experiment_assignments_experiment_id ON experiment_assignments(experiment_id);
CREATE INDEX idx_experiment_assignments_variant ON experiment_assignments(variant);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiments ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_flags ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE cohort_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_assignments ENABLE ROW LEVEL SECURITY;

-- USERS: Users see only their own data
CREATE POLICY "Users can view their own profile"
  ON users FOR SELECT
  USING (auth.uid()::text = user_id OR auth.jwt() ->> 'role' = 'admin' OR auth.jwt() ->> 'role' = 'product_team');

CREATE POLICY "Users can update their own profile"
  ON users FOR UPDATE
  USING (auth.uid()::text = user_id);

-- Product team can see aggregated user data (no individual emails)
CREATE POLICY "Product team can view aggregated stats"
  ON users FOR SELECT
  USING (auth.jwt() ->> 'role' = 'product_team');

-- EVENTS: Users see only their own events
CREATE POLICY "Users can view their own events"
  ON events FOR SELECT
  USING (user_id = (SELECT id FROM users WHERE user_id = auth.uid()::text) OR auth.jwt() ->> 'role' = 'admin' OR auth.jwt() ->> 'role' = 'product_team');

CREATE POLICY "Users can insert their own events"
  ON events FOR INSERT
  WITH CHECK (user_id = (SELECT id FROM users WHERE user_id = auth.uid()::text));

-- EXPERIMENTS: Product team and admins only
CREATE POLICY "Product team can view experiments"
  ON experiments FOR SELECT
  USING (auth.jwt() ->> 'role' = 'product_team' OR auth.jwt() ->> 'role' = 'admin');

-- NOTIFICATIONS: Users see only their own notifications
CREATE POLICY "Users can view their own notifications"
  ON notifications FOR SELECT
  USING (user_id = (SELECT id FROM users WHERE user_id = auth.uid()::text) OR auth.jwt() ->> 'role' = 'admin');

-- NOTIFICATION PREFERENCES: Users manage their own preferences
CREATE POLICY "Users can view their own preferences"
  ON notification_preferences FOR SELECT
  USING (user_id = (SELECT id FROM users WHERE user_id = auth.uid()::text) OR auth.jwt() ->> 'role' = 'admin');

CREATE POLICY "Users can update their own preferences"
  ON notification_preferences FOR UPDATE
  USING (user_id = (SELECT id FROM users WHERE user_id = auth.uid()::text));

-- RECOMMENDATIONS: Users see only their own recommendations
CREATE POLICY "Users can view their own recommendations"
  ON recommendations FOR SELECT
  USING (user_id = (SELECT id FROM users WHERE user_id = auth.uid()::text) OR auth.jwt() ->> 'role' = 'admin');

-- COHORT ASSIGNMENTS: Product team for analysis, admins for all
CREATE POLICY "Product team can view cohort assignments"
  ON cohort_assignments FOR SELECT
  USING (auth.jwt() ->> 'role' = 'product_team' OR auth.jwt() ->> 'role' = 'admin');

-- EXPERIMENT ASSIGNMENTS: Product team for analysis
CREATE POLICY "Product team can view experiment assignments"
  ON experiment_assignments FOR SELECT
  USING (auth.jwt() ->> 'role' = 'product_team' OR auth.jwt() ->> 'role' = 'admin');

-- ============================================================================
-- MATERIALIZED VIEWS FOR ANALYSIS
-- ============================================================================

-- User engagement metrics (refreshed daily)
CREATE MATERIALIZED VIEW user_engagement_summary AS
SELECT
  u.id,
  u.user_id,
  u.engagement_score,
  u.engagement_tier,
  COUNT(CASE WHEN e.timestamp > NOW() - INTERVAL '7 days' THEN e.id END) as events_7d,
  COUNT(CASE WHEN e.timestamp > NOW() - INTERVAL '30 days' THEN e.id END) as events_30d,
  MAX(e.timestamp) as last_event_at,
  (NOW()::date - u.created_at::date) as days_since_signup
FROM users u
LEFT JOIN events e ON u.id = e.user_id
GROUP BY u.id, u.user_id, u.engagement_score, u.engagement_tier;

CREATE INDEX idx_user_engagement_summary_tier ON user_engagement_summary(engagement_tier);
CREATE INDEX idx_user_engagement_summary_score ON user_engagement_summary(engagement_score);

-- Cohort distribution
CREATE MATERIALIZED VIEW cohort_distribution AS
SELECT
  lifecycle_stage,
  behavioral_cohort,
  goal_cluster,
  engagement_tier,
  COUNT(*) as user_count,
  AVG(engagement_score)::NUMERIC(5,2) as avg_engagement_score
FROM cohort_assignments ca
JOIN users u ON ca.user_id = u.id
WHERE ca.assigned_at = (
  SELECT MAX(assigned_at) FROM cohort_assignments WHERE user_id = u.id
)
GROUP BY lifecycle_stage, behavioral_cohort, goal_cluster, engagement_tier;

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to update user engagement score and cohort
CREATE OR REPLACE FUNCTION update_user_engagement()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE users
  SET updated_at = NOW()
  WHERE id = NEW.user_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_user_engagement
AFTER INSERT ON events
FOR EACH ROW
EXECUTE FUNCTION update_user_engagement();

-- Function to refresh materialized views
CREATE OR REPLACE FUNCTION refresh_engagement_views()
RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY user_engagement_summary;
  REFRESH MATERIALIZED VIEW CONCURRENTLY cohort_distribution;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS
-- ============================================================================
COMMENT ON TABLE users IS 'Core user profile with engagement metrics and cohort classification';
COMMENT ON TABLE events IS 'User activity events for behavior tracking and analysis';
COMMENT ON TABLE experiments IS 'A/B test configuration and metadata';
COMMENT ON TABLE feature_flags IS 'Feature flag definitions with rollout and targeting';
COMMENT ON TABLE notifications IS 'Notification delivery history and engagement tracking';
COMMENT ON TABLE recommendations IS 'Personalized content recommendations with reason and performance';
COMMENT ON TABLE cohort_assignments IS 'Historical record of user segment assignments';
COMMENT ON TABLE experiment_assignments IS 'Track experiment exposure and variant assignment';
