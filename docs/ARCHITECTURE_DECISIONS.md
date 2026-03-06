# Architecture Decision Records

This document captures the key architectural decisions made during the design and build of the Engagement & Personalization Engine. Each ADR explains the context, decision, alternatives considered, and trade-offs.

---

## ADR-001: Event-Driven Architecture with Segment and Kafka for Data Ingestion

**Status:** Accepted
**Date:** 2024-12
**Context:** The platform needed to ingest user activity events (content views, completions, goal actions, social interactions, notification responses) from mobile and web clients and make them available for real-time scoring, batch feature computation, and warehouse analytics. The system had to handle event volumes from 2M+ weekly active users while supporting both real-time and batch consumption patterns. Events needed to flow to multiple downstream consumers: the engagement scorer (real-time), Snowflake (batch analytics), and the recommendation engine (nightly batch).
**Decision:** Adopt Segment as the Customer Data Platform (CDP) for event collection, identity resolution, and warehouse sync. Use Kafka as the internal event streaming backbone for decoupled, multi-consumer event processing. Raw events flow from clients through Segment, which routes them to both Snowflake (via warehouse sync) and Kafka (via webhook/connector). Internal services (scoring, segmentation, notification orchestration) consume from Kafka topics.
**Alternatives Considered:**
- **Direct client-to-API event ingestion:** Simpler but creates tight coupling between client SDKs and backend services. No identity resolution, no replay capability, no built-in warehouse sync. Would require building event schema validation, deduplication, and routing from scratch.
- **Kafka-only without Segment:** Lower cost but loses Segment's identity resolution (cross-device user stitching), pre-built warehouse connectors, and client SDK ecosystem. Would need to build identity resolution and warehouse loading pipelines.
- **AWS Kinesis instead of Kafka:** Managed service reduces ops burden but creates vendor lock-in and lacks Kafka's ecosystem of connectors and tooling. Kafka UI for local development was a significant developer experience advantage.
**Consequences:** Segment adds monthly cost ($500-2K depending on volume tier) but eliminates the need to build identity resolution and warehouse sync. Kafka provides replay capability for reprocessing events when scoring logic changes. The docker-compose.yml includes Zookeeper, Kafka, and Kafka UI for local development parity. The trade-off is operational complexity: Kafka requires monitoring for consumer lag, partition rebalancing, and topic retention policies.

---

## ADR-002: Composite Weighted Engagement Score (0-100) with Five Components

**Status:** Accepted
**Date:** 2024-12
**Context:** The platform needed a single numeric indicator of user engagement health that could drive segmentation, personalization, intervention triggers, and experiment targeting. The existing DAU/MAU ratio was too coarse -- a user who opens the app daily but never completes meaningful actions looks "engaged" by DAU/MAU but is not receiving value. The score needed to capture multiple dimensions of engagement and be computable in real-time on every meaningful event.
**Decision:** Implement a composite engagement score from 0 to 100, computed as a weighted sum of five components: recency (0.30), frequency (0.25), depth (0.20), consistency (0.15), and progression (0.10). Each component is independently scored 0-100 using stepped decay functions (not linear), then combined via fixed weights. The score is cached in Redis for sub-millisecond retrieval (key: `engagement:{user_id}`, TTL: 24h) and the score history is stored in Snowflake for trend analysis.
**Alternatives Considered:**
- **Single metric (DAU/MAU):** Too coarse. Cannot distinguish a user who opens the app daily from one who completes meaningful actions daily. AUC for churn prediction with DAU/MAU alone was 0.68 vs. 0.84 with the composite score.
- **Equal weights across all components (20/20/20/20/20):** Tested and produced AUC 0.76 for 30-day churn prediction. The calibrated weights (30/25/20/15/10) yielded AUC 0.84, a meaningful improvement driven primarily by the higher recency weight.
- **ML-learned weights via logistic regression:** Trained model learned similar weight distribution (recency highest), validating the hand-tuned weights. However, a fully ML-learned score is harder to explain to product stakeholders and harder to debug when individual user scores seem wrong. The hand-tuned approach with ML validation strikes the right balance.
- **Percentile-based tiers:** Tiers based on user distribution (top 20% = Tier 1) would shift as the user base changes, making historical comparisons meaningless. Fixed boundaries (80-100 = Tier 1) allow the distribution to improve over time as personalization takes effect.
**Consequences:** Recency at 30% weight means the score is highly sensitive to inactivity. A user who was a power user last week but hasn't logged in for 3 days will see a significant score drop. This is intentional: it triggers early intervention before the user fully disengages. The trade-off is that the score can feel "volatile" for users with irregular but healthy usage patterns (e.g., weekend-only users). The consistency component (15% weight) partially compensates for this by rewarding regular patterns regardless of frequency.

---

## ADR-003: Deterministic Hash-Based Experiment Assignment with Server-Side Evaluation

**Status:** Accepted
**Date:** 2025-01
**Context:** The experimentation framework needed to support 50+ concurrent experiments per quarter with deterministic, cross-platform assignment (same user gets same variant on iOS, Android, and web). Assignment needed to be stateless (no database lookup on the hot path), support mutual exclusion groups, segment targeting, progressive rollout, and long-term holdouts. The system also needed exposure logging (distinguishing assignment from actual exposure) for intent-to-treat analysis.
**Decision:** Use SHA-256 hash of `user_id:experiment_id` to compute a deterministic bucket (0-99). Bucket-to-variant mapping uses cumulative weight ranges. Assignment evaluation follows a strict priority chain: experiment status check, segment targeting, mutual exclusion, rollout percentage, then bucket computation. Exposure events are logged separately from assignment events. A 5% long-term holdout is maintained per experiment for persistent effect measurement.
**Alternatives Considered:**
- **Client-side assignment (Optimizely, LaunchDarkly):** Polished out-of-box solution but neither supported sequential testing with engagement-aware cohort decomposition at the time. Optimizely license was $180K/year. Client-side assignment also introduces flickering (variant switches on page load) and cannot guarantee cross-platform consistency without server coordination.
- **Random assignment with database persistence:** Simpler to implement but requires a database lookup on every assignment check. At 2M+ WAU with multiple experiments, this creates unacceptable latency and database load. Deterministic hashing eliminates the need for persistence on the hot path.
- **PostHog built-in experiments (Phase 2):** Adopted for the modern stack iteration. PostHog handles assignment, exposure logging, and basic analysis. The custom framework remains for advanced features (sequential testing with O'Brien-Fleming boundaries, custom metric decomposition by engagement tier, SRM detection).
**Consequences:** Deterministic hashing means assignment is computed, not stored. This eliminates database bottlenecks but makes it impossible to reassign a user to a different variant mid-experiment without changing the experiment ID. The SHA-256 approach was validated across 1M synthetic IDs with deviation less than 0.05%. The trade-off is that the custom assignment engine requires ongoing maintenance, while a managed service like PostHog would reduce this burden. The Phase 2 migration to PostHog for basic experiments addresses this.

---

## ADR-004: Two-Stage Recommendation Architecture (Candidate Generation + Ranking)

**Status:** Accepted
**Date:** 2025-01
**Context:** The recommendation engine needed to serve personalized content feeds within a 100ms API latency budget. The content catalog contains 2,000+ items. Running the full ranking model (collaborative filtering + content affinity + tier adjustment + goal relevance + freshness) on every item would take approximately 300ms, exceeding the budget. The engine also needed a graceful degradation path when the ML model (SageMaker collaborative filtering) is unavailable.
**Decision:** Implement a two-stage architecture. Stage 1 (Candidate Generation) applies cheap O(n) filters to reduce the catalog to approximately 100 items: remove completed content, apply 48-hour dedup, filter by goal cluster relevance, and cap by recency times popularity. Stage 2 (Ranking) runs the full weighted scoring model on the filtered candidates. Post-ranking diversity enforcement ensures no more than 2 items from the same category and 3 from the same content type in the top 10. A rule-based fallback ranking (goal relevance times recency times popularity) activates when SageMaker is unavailable, providing a non-personalized but functional feed.
**Alternatives Considered:**
- **Single-stage full catalog ranking:** Simplest architecture but 300ms latency is unacceptable. Users perceive delays above 200ms as sluggish.
- **Pre-computed recommendations (nightly batch only):** The Trigger.dev recommendation generation job already does this for the nightly batch. However, pre-computed recommendations go stale within hours as new content is published and user context changes. The real-time two-stage approach handles intra-day changes.
- **Approximate nearest neighbor (ANN) search:** Libraries like FAISS or ScaNN can search embeddings at sub-millisecond latency. However, this requires maintaining content embeddings and a serving infrastructure. The two-stage filter-then-rank approach is simpler and sufficient at current catalog size (2K items). ANN becomes necessary at 50K+ items.
**Consequences:** The two-stage approach achieves approximately 55ms total ranking time within the 100ms API budget (leaving room for Redis lookups and serialization). The 20% discovery allowance in goal filtering (random items from unrelated clusters) prevents filter bubbles. The fallback ranking is indistinguishable to the user -- no error states or "recommendations unavailable" messages. The trade-off is that candidate generation filters are coarse and may exclude items that the ranking model would have scored highly.

---

## ADR-005: Supabase (PostgreSQL + Row Level Security) as Primary Database with Redis Cache

**Status:** Accepted
**Date:** 2025-01
**Context:** The system needed a primary database for storing user profiles, experiment configurations, feature flag definitions, notification history, cohort assignments, and recommendation results. The database needed to support Row Level Security for multi-tenant data isolation (users see only their own data, product team sees aggregates, admins see everything). Real-time features (engagement scores, segment membership, feature flag configs) needed sub-millisecond read latency, which PostgreSQL cannot provide at scale.
**Decision:** Use Supabase (managed PostgreSQL with built-in RLS, real-time subscriptions, and auth) as the primary datastore. All tables have RLS policies: users can only read/write their own data, product team roles can view experiment and cohort data, admin roles have full access. Redis serves as the real-time cache layer for three high-frequency access patterns: engagement scores (key: `engagement:{user_id}`, TTL: 24h), segment membership (key: `segments:{user_id}`, TTL: 1h), and feature flag configs (key: `flag:{flag_key}`, TTL: 5min with pub/sub invalidation). Snowflake serves as the analytical warehouse for event storage, feature computation, and experiment analysis.
**Alternatives Considered:**
- **Self-hosted PostgreSQL:** Full control but requires managing backups, failover, connection pooling, and security patches. Supabase provides these out of the box plus RLS integration with JWT-based auth.
- **DynamoDB for real-time data:** Sub-millisecond reads without Redis, but loses relational capabilities needed for experiment assignment queries (joins between users, experiments, and assignments). DynamoDB's query model is too restrictive for the analytical queries the product team needs.
- **Redis as primary store (no PostgreSQL):** Redis provides the latency profile needed but lacks durability guarantees, relational query capability, and transactional integrity. Engagement scores can be recomputed from events if Redis data is lost, but experiment assignments and user profiles cannot.
**Consequences:** The three-tier storage architecture (Supabase for durable state, Redis for hot cache, Snowflake for analytics) introduces operational complexity. Data consistency between tiers requires careful cache invalidation. The TTL-based approach (24h for scores, 1h for segments, 5min for flags) accepts eventual consistency in exchange for simplicity. Feature flag changes propagate within 5 minutes via TTL expiry (or instantly via pub/sub invalidation in production). The trade-off is that a user might see a stale flag value for up to 5 minutes after a flag is updated.

---

## ADR-006: Feature Flags as Separate Infrastructure from Experiments

**Status:** Accepted
**Date:** 2025-01
**Context:** The platform needed both feature flags (for progressive rollout and operational control) and experiments (for measuring the impact of changes). Early designs combined these into a single system where every flag was also an experiment. This created operational confusion: flags that were fully rolled out (100%) were still tracked as "experiments," experiment analysis included users who were in the rollout but not being measured, and killing a flag for operational reasons corrupted experiment results.
**Decision:** Maintain feature flags and experiments as separate systems with distinct lifecycles and data models. Flags are permanent infrastructure for operational control: progressive rollout (1% to 5% to 20% to 50% to 100%), kill switches, segment targeting, allowlist/blocklist overrides, and dependency chains. Experiments are temporary and measure impact: they have hypotheses, primary metrics, guardrail metrics, sample size calculations, and ship/iterate/kill decisions. A flag can gate an experiment variant (the `experiment_id` field on `FeatureFlag`), but they are managed independently. Flags have a staleness detector that alerts when a flag has not been updated in 30+ days, prompting cleanup.
**Alternatives Considered:**
- **Combined flag/experiment system:** Simpler to build but creates lifecycle confusion. A flag at 100% rollout is "done" from an operational perspective but might still be running as an experiment. Killing a flag for a production incident would corrupt the experiment's intent-to-treat analysis.
- **Experiments only (no separate flags):** Every rollout becomes an experiment with control/treatment. This forces measurement overhead on routine deployments and makes it impossible to do operational rollouts without statistical machinery.
- **Third-party combined platform (LaunchDarkly):** Provides both flags and experiments in one product but at significant cost ($180K+/year at scale) and with less control over statistical methodology.
**Consequences:** The separation means two systems to maintain, two evaluation paths, and two sets of audit logs. However, it provides clean operational boundaries: the on-call engineer can kill a flag without worrying about experiment integrity, and the data scientist can stop an experiment without affecting the feature rollout. The progressive rollout manager (`ProgressiveRollout` class) bridges the two systems by managing staged rollout with monitoring criteria at each stage (1% to 5% to 20% to 50% to 100%), preventing the rollout incidents that occurred before this system was in place.
