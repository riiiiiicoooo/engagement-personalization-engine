# Production Readiness Checklist

Checklist for evaluating the production readiness of the Engagement & Personalization Engine. Items marked `[x]` are implemented in the current codebase. Items marked `[ ]` are not yet present and should be addressed before or during production deployment.

---

## Security

### Authentication & Authorization
- [x] Row Level Security (RLS) enabled on all database tables (users, events, experiments, feature_flags, notifications, notification_preferences, recommendations, cohort_assignments, experiment_assignments)
- [x] RLS policies enforce user-scoped data access (users can only read/write their own data)
- [x] Role-based access control via JWT claims (admin, product_team roles for experiment and cohort data)
- [x] Product team restricted from viewing individual user emails (aggregated stats only policy)
- [x] Supabase service role key separated from anon key in environment configuration
- [ ] API authentication middleware (JWT validation on all API endpoints)
- [ ] Rate limiting on public-facing API endpoints
- [ ] CORS policy configured for allowed origins
- [ ] API key rotation policy and automated rotation schedule

### Secrets Management
- [x] Environment variables used for all secrets (Supabase keys, PostHog API key, Resend API key, Trigger.dev key, Segment write key, AWS credentials)
- [x] `.env.example` file documents all required environment variables without exposing real values
- [x] `.gitignore` excludes `.env` files from version control
- [ ] Secrets stored in a managed secrets service (AWS Secrets Manager, Vault, or Doppler) rather than environment variables
- [ ] Secret scanning enabled in CI pipeline to prevent accidental commits

### TLS & Network Security
- [ ] TLS enforced on all external connections (API, database, Redis, Kafka)
- [ ] Redis configured with TLS in production (local docker-compose uses `requirepass` only)
- [ ] Kafka configured with SASL/TLS authentication (local docker-compose uses PLAINTEXT)
- [ ] Database connections use SSL mode `require` or `verify-full`
- [ ] Network segmentation between application tier and data tier

### PII Handling
- [x] User email stored in users table with unique constraint
- [x] Notification preferences table allows users to control their own data (disable_all, do_not_disturb)
- [x] Events table stores user_id as foreign key reference, not raw PII in event properties
- [ ] PII fields encrypted at rest (email, user identifiers)
- [ ] Data anonymization pipeline for analytical queries (hash emails before export to Snowflake)
- [ ] PII access audit logging (who accessed which user's data and when)
- [ ] Data classification labels on database columns containing PII

---

## Reliability

### High Availability & Failover
- [x] PostgreSQL health check configured in docker-compose (pg_isready with retries)
- [x] Redis health check configured in docker-compose (redis-cli ping with retries)
- [x] Kafka health check configured in docker-compose (broker API versions check with retries)
- [x] Recommendation engine has fallback ranking when ML model (SageMaker) is unavailable
- [x] Feature flag evaluation returns default value when flag not found or service is down
- [x] Feature flag kill switch provides instant emergency disable (propagation under 1 second)
- [ ] Multi-region database deployment with read replicas
- [ ] Redis cluster or sentinel configuration for automatic failover
- [ ] Kafka multi-broker deployment with replication factor greater than 1 (currently set to 1)
- [ ] Circuit breaker pattern on external service calls (Segment, PostHog, SageMaker, Resend)
- [ ] Health check endpoints on application services (liveness and readiness probes)

### Backup & Recovery
- [x] PostgreSQL data persisted via Docker volume (postgres_data)
- [x] Redis data persisted via Docker volume with append-only file (redis_data, appendonly yes)
- [x] Kafka data persisted via Docker volume (kafka_data)
- [ ] Automated database backup schedule (daily full, hourly incremental)
- [ ] Point-in-time recovery (PITR) enabled for PostgreSQL
- [ ] Backup restoration tested and documented with RTO/RPO targets
- [ ] Disaster recovery runbook documented

### Idempotency & Data Integrity
- [x] Experiment assignments use UNIQUE constraint on (user_id, experiment_id) to prevent duplicate assignments
- [x] Deterministic hash-based experiment assignment ensures same user always gets same variant (no flickering)
- [x] Deterministic hash-based feature flag evaluation produces consistent results across evaluations
- [x] Trigger.dev engagement scoring job implements checkpointing for resuming after failures
- [x] Trigger.dev recommendation job uses Promise.allSettled for partial failure tolerance (continues on individual user errors)
- [x] Batch processing in engagement scoring continues with next batch on error rather than failing entire job
- [ ] Event deduplication at ingestion layer (idempotency keys on event writes)
- [ ] Idempotent API endpoints using request-level idempotency keys
- [ ] Database migration rollback scripts for each migration

### Graceful Degradation
- [x] Recommendation engine fallback to rule-based ranking (goal relevance x recency x popularity) when collaborative filtering model is unavailable
- [x] Feature flag evaluation returns default value on any error condition
- [x] Engagement scorer handles missing data with neutral defaults (e.g., consistency score defaults to 50 with insufficient data)
- [x] Goal cluster assignment defaults to GENERAL_WELLNESS when no onboarding data or behavioral signals exist
- [x] Notification orchestration workflow checks user notification preferences before sending (respects disable_all)
- [ ] Client-side feature flag cache with stale-while-revalidate pattern
- [ ] Offline-capable scoring for mobile clients

---

## Observability

### Logging
- [x] Trigger.dev jobs log progress with percentage completion during batch processing
- [x] Trigger.dev jobs log error details for failed batches with user context
- [x] Feature flag evaluation audit trail logged (flag_key, user_id, value, rule_matched, timestamp)
- [x] Engagement score events serialized with full component breakdown for debugging
- [x] PostgreSQL configured with log_statement=all for query logging in development
- [ ] Structured logging format (JSON) with correlation IDs across services
- [ ] Log aggregation service (Datadog Logs, CloudWatch Logs, or ELK stack)
- [ ] Log retention policy configured (30 days hot, 90 days warm, 1 year cold)
- [ ] Sensitive data scrubbed from log output (emails, tokens)

### Metrics
- [x] Engagement score components tracked individually (recency, frequency, depth, consistency, progression) enabling root-cause analysis of score changes
- [x] Experiment results track sample size, lift percentage, p-value, confidence intervals, and Bayesian probability
- [x] Cohort distribution materialized view provides aggregate metrics refreshable via stored function
- [x] Feature quality metrics table in Snowflake tracks null rates, min/max/mean/stddev per feature per day
- [x] PostHog custom events defined for full event taxonomy (40+ event types across lifecycle, content, engagement, notification, experiment, and recommendation categories)
- [ ] Application metrics exported to monitoring system (request latency p50/p95/p99, error rates, throughput)
- [ ] Redis cache hit rate monitoring
- [ ] Kafka consumer lag monitoring
- [ ] Feature flag evaluation latency tracking (target: less than 5ms p95)
- [ ] Recommendation engine latency tracking (target: less than 55ms for ranking)

### Tracing
- [ ] Distributed tracing (OpenTelemetry or Datadog APM) across API, scoring, recommendation, and experiment services
- [ ] Trace context propagation through Kafka messages
- [ ] Trace sampling strategy configured (100% for errors, 10% for normal traffic)
- [ ] Slow query tracing for PostgreSQL (queries exceeding 100ms)

### Alerting
- [x] Engagement score alert detection for rapid decline (score drop greater than 15 points in 3 days), tier demotion, approaching dormancy, and reactivation
- [x] Experiment guardrail monitoring with auto-stop capability when guardrail metrics are breached
- [x] Sample Ratio Mismatch (SRM) detection with chi-squared test (threshold p < 0.001)
- [x] Feature flag staleness detection alerts for flags not updated in 30+ days
- [x] Progressive rollout halts on monitoring criteria failure (error rate, latency, crash rate thresholds)
- [ ] PagerDuty or Opsgenie integration for on-call alerting
- [ ] Alert routing by severity (P1: page, P2: Slack, P3: ticket)
- [ ] Alert runbooks linked to each alert type
- [ ] SLA breach alerting (API latency exceeding 200ms for more than 5 minutes)

---

## Performance

### Caching
- [x] Engagement scores cached in Redis (key: `engagement:{user_id}`, TTL: 24 hours)
- [x] User segment membership cached in Redis (key: `segments:{user_id}`, TTL: 1 hour)
- [x] Feature flag configurations cached in Redis (key: `flag:{flag_key}`, TTL: 5 minutes)
- [x] Feature flag cache invalidation via pub/sub on flag update (production design)
- [x] Materialized views in PostgreSQL for user engagement summary and cohort distribution (refreshable concurrently)
- [x] Snowflake dynamic table for ML features with 1-hour target lag
- [ ] Cache warming strategy on service startup
- [ ] Cache eviction monitoring and capacity planning
- [ ] Client-side caching headers on API responses

### Throughput & Latency
- [x] Recommendation engine designed for 55ms ranking latency within 100ms total API budget
- [x] Feature flag evaluation target of less than 5ms (p95) via in-memory evaluation from cached config
- [x] Two-stage recommendation architecture (filter to 100 candidates, then rank) to meet latency budget
- [x] Batch processing in Trigger.dev jobs with configurable batch size (100 for scoring, 50 for recommendations)
- [x] Database indexes on high-query columns (user_id, event_type, timestamp, lifecycle_stage, engagement_tier, flag_id, experiment_id)
- [x] Composite indexes for common query patterns (events.user_id + timestamp, recommendations.user_id + created_at)
- [ ] Connection pooling for PostgreSQL (PgBouncer or Supabase connection pooler)
- [ ] API response compression (gzip/brotli)
- [ ] Database query plan analysis and optimization for top 10 queries

### Load Testing
- [ ] Load test suite for API endpoints (target: 1000 RPS sustained)
- [ ] Load test for feature flag evaluation path (target: 10,000 evaluations/second)
- [ ] Load test for engagement scoring pipeline (target: 10,000 users scored in under 5 minutes)
- [ ] Load test for recommendation generation (target: 100 users scored concurrently)
- [ ] Chaos engineering tests (Redis failure, Kafka unavailability, database connection exhaustion)

---

## Compliance

### GDPR
- [x] Notification preferences allow users to opt out of all notifications (disable_all flag)
- [x] Notification preferences support do-not-disturb windows (do_not_disturb_start, do_not_disturb_end)
- [x] Users can view their own data via RLS-protected API access
- [x] Re-engagement email includes link to update notification preferences
- [x] ON DELETE CASCADE configured on foreign key relationships (deleting a user removes their events, notifications, recommendations, assignments)
- [ ] Right to erasure (GDPR Article 17) endpoint that deletes all user data across PostgreSQL, Redis, Snowflake, and Segment
- [ ] Data export endpoint (GDPR Article 20) that returns all user data in machine-readable format
- [ ] Consent tracking for data processing activities
- [ ] Data Processing Agreement (DPA) with all sub-processors (Supabase, PostHog, Segment, Snowflake, Resend)

### CCPA
- [ ] "Do Not Sell My Personal Information" mechanism
- [ ] Consumer data access request handling within 45-day window
- [ ] Categories of personal information collected documented and disclosed
- [ ] Service provider agreements with all third parties processing user data

### Audit Logging
- [x] Feature flag evaluation audit events logged (flag_key, user_id, value, rule_matched, timestamp)
- [x] Experiment exposure events logged separately from assignment events (surface, exposed_at)
- [x] Cohort transition events tracked with previous and current state (lifecycle_stage, behavioral_cohort, engagement_tier, goal_cluster)
- [x] Engagement score update events include full component breakdown and delta from previous score
- [x] Notification delivery history tracked with full lifecycle (pending, sent, failed, bounced, opened, clicked)
- [ ] Admin action audit log (who changed what experiment/flag configuration and when)
- [ ] Audit log immutability (write-once storage, tamper detection)
- [ ] Audit log retention policy (minimum 7 years for financial compliance)

### Data Retention
- [x] Recommendation records include expires_at field for TTL-based cleanup
- [x] Feature computation pipeline uses 14-day lookback window (older raw events not needed for features)
- [ ] Automated data retention enforcement (delete events older than N days)
- [ ] Tiered retention policy (hot: 30 days in PostgreSQL, warm: 1 year in Snowflake, cold: archive)
- [ ] Data retention policy documented and aligned with privacy policy
- [ ] Snowflake time travel and fail-safe configuration for regulatory hold

---

## Deployment

### CI/CD
- [x] Vercel deployment configuration present (vercel.json)
- [x] Supabase migration file for database schema (001_initial_schema.sql)
- [x] Makefile present for common development operations
- [x] Docker Compose configuration for local development environment parity
- [ ] Automated CI pipeline (lint, type check, unit tests, integration tests on every PR)
- [ ] Automated CD pipeline (deploy to staging on merge to main, promote to production on approval)
- [ ] Database migration automation (run pending migrations as part of deploy)
- [ ] Deployment notifications to Slack/Teams channel

### Rollback
- [x] Feature flag kill switch enables instant rollback of any flagged feature (propagation under 1 second)
- [x] Progressive rollout manager can halt advancement at any stage if monitoring criteria fail
- [x] Experiment auto-stop on guardrail breach provides automatic rollback of experiment variants
- [ ] Application version rollback procedure documented (Vercel instant rollback, or blue-green swap)
- [ ] Database migration rollback scripts tested
- [ ] Rollback runbook with decision criteria and escalation path

### Blue-Green / Canary
- [x] Progressive rollout system implements canary deployment pattern for features (1% to 5% to 20% to 50% to 100% with monitoring at each stage)
- [x] Rollout stages have defined duration thresholds (4h canary, 12h early access, 24h limited, 48h broad)
- [x] Monitoring halt conditions defined per stage (error rate increase over 0.1%, latency increase over 50ms p95, crash rate increase over 0.5%)
- [ ] Infrastructure-level blue-green deployment for zero-downtime releases
- [ ] Traffic splitting at load balancer level for infrastructure canary deployments
- [ ] Automated canary analysis with statistical comparison between canary and baseline

### Environment Parity
- [x] Docker Compose provides local development environment with PostgreSQL, Redis, Kafka, Zookeeper, and Kafka UI
- [x] All services configured on shared Docker network for inter-service communication
- [x] Health checks configured on all infrastructure services with retry logic
- [x] Environment variable configuration documented in .env.example for all required services
- [ ] Staging environment that mirrors production configuration
- [ ] Infrastructure as Code (Terraform, Pulumi, or CDK) for production infrastructure
- [ ] Environment promotion workflow (dev to staging to production)
