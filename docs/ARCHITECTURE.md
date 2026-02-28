# System Architecture: Engagement & Personalization Engine

**Last Updated:** January 2025

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                    │
│                                                                          │
│  ┌──────────────────────┐           ┌──────────────────────┐            │
│  │ Mobile App            │           │ Web App               │            │
│  │ (React Native)        │           │ (Next.js)             │            │
│  │                       │           │                       │            │
│  │ Personalized feed     │           │ Personalized dashboard│            │
│  │ Feature flag eval     │           │ Feature flag eval     │            │
│  │ Event tracking SDK    │           │ Event tracking SDK    │            │
│  │ Push notification     │           │ In-app messaging      │            │
│  │ handling              │           │                       │            │
│  └───────────┬───────────┘           └───────────┬───────────┘            │
│              │                                    │                      │
└──────────────┼────────────────────────────────────┼──────────────────────┘
               │                                    │
               └─────────────┬──────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       EVENT COLLECTION (Segment)                         │
│                                                                          │
│  Client SDKs → Segment → Fan out to:                                    │
│  ├── Snowflake (warehouse, batch analytics, experiment analysis)         │
│  ├── Redis (real-time engagement score updates)                          │
│  ├── Amplitude (product analytics dashboards)                            │
│  └── OneSignal (notification delivery)                                   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       API LAYER (FastAPI)                                 │
│                                                                          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐           │
│  │ Personali- │ │ Experiment │ │ Feature    │ │ Engagement │           │
│  │ zation API │ │ API        │ │ Flag API   │ │ Score API  │           │
│  │            │ │            │ │            │ │            │           │
│  │ /recommend │ │ /assign    │ │ /evaluate  │ │ /score     │           │
│  │ /feed      │ │ /expose    │ │ /flags     │ │ /predict   │           │
│  │ /intervene │ │ /results   │ │ /config    │ │ /segment   │           │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘           │
│        │              │              │              │                   │
└────────┼──────────────┼──────────────┼──────────────┼───────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       SERVICE LAYER                                      │
│                                                                          │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────────────────┐  │
│  │ Recommendation  │ │ Experiment     │ │ Engagement Scoring         │  │
│  │ Engine          │ │ Engine         │ │ Engine                     │  │
│  │                 │ │                │ │                            │  │
│  │ Collaborative   │ │ Assignment     │ │ Real-time composite score  │  │
│  │ filtering       │ │ (hash-based)   │ │ Churn prediction model    │  │
│  │ Content affinity│ │ Exposure log   │ │ Risk detection             │  │
│  │ Diversity       │ │ Guardrails     │ │ Intervention triggers      │  │
│  │ enforcement     │ │ Auto-stop      │ │ Segment assignment         │  │
│  │ Fallback ranking│ │ Sequential     │ │                            │  │
│  │                 │ │ testing        │ │                            │  │
│  └────────────────┘ └────────────────┘ └────────────────────────────┘  │
│                                                                          │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────────────────┐  │
│  │ Feature Flag   │ │ Notification   │ │ Segmentation               │  │
│  │ Engine         │ │ Optimizer      │ │ Engine                     │  │
│  │                │ │                │ │                            │  │
│  │ Rule eval      │ │ Send time      │ │ Lifecycle stage            │  │
│  │ Rollout %      │ │ optimization   │ │ Behavioral cohort          │  │
│  │ Kill switch    │ │ Frequency cap  │ │ Goal cluster               │  │
│  │ Segment target │ │ Channel select │ │ Engagement tier            │  │
│  │ Audit log      │ │ Escalation     │ │ Custom segments (PM rules) │  │
│  └────────────────┘ └────────────────┘ └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                         │
│                                                                          │
│  ┌───────────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ PostgreSQL         │  │ Redis        │  │ Snowflake                │ │
│  │                    │  │              │  │                          │ │
│  │ Experiment configs │  │ Flag values  │  │ Event warehouse          │ │
│  │ Flag definitions   │  │ Engagement   │  │ User behavioral profiles │ │
│  │ Segment rules      │  │ scores       │  │ Experiment results       │ │
│  │ User profiles      │  │ Assignments  │  │ Cohort tables            │ │
│  │ Assignments        │  │ Session data │  │ ML training data         │ │
│  │ Intervention log   │  │ Rate limits  │  │ Feature store tables     │ │
│  └───────────────────┘  └──────────────┘  └──────────────────────────┘ │
│                                                                          │
│  ┌───────────────────┐  ┌──────────────────────────────────────────┐   │
│  │ Feature Store      │  │ ML Models (SageMaker)                    │   │
│  │ (Feast on          │  │                                          │   │
│  │  Snowflake)        │  │ Churn prediction (gradient boosting)     │   │
│  │                    │  │ Content ranking (collaborative filter)   │   │
│  │ Training features  │  │ Engagement scoring (regression)          │   │
│  │ Serving features   │  │ User clustering (k-means)               │   │
│  │ Point-in-time      │  │ Send time optimization (regression)     │   │
│  │ correct joins      │  │                                          │   │
│  └───────────────────┘  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Services

### 2.1 Personalization Service

Serves personalized content on every app open. Latency budget: 100ms (p95). This is on the critical path — if it's slow, the app feels slow.

```
Client requests personalized feed
              │
              ▼
┌──────────────────────────────┐
│ Fetch user context (parallel) │  Total: ~20ms
│                               │
│ Redis:                        │
│ ├── engagement_score          │  < 1ms (cache hit)
│ ├── segment_memberships       │  < 1ms (cache hit)
│ ├── active_experiments        │  < 1ms (cache hit)
│ └── feature_flag_values       │  < 1ms (cache hit)
│                               │
│ PostgreSQL (if cache miss):   │
│ ├── user_profile              │  ~5ms
│ └── content_interaction_hist  │  ~10ms
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Generate candidate pool       │  ~15ms
│                               │
│ Content catalog filtered by:  │
│ ├── Goal cluster relevance    │
│ ├── Lifecycle stage fit       │
│ ├── Not seen in 48 hours      │
│ └── Not completed previously  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Rank candidates               │  ~40ms
│                               │
│ Score = (                     │
│   0.40 × collab_filter_score  │  "Users like you engaged with X"
│   0.25 × content_affinity     │  Past interaction pattern match
│   0.15 × freshness_boost      │  New content temporary lift
│   0.10 × engagement_tier_adj  │  Tier 4-5 get simpler content
│   0.10 × goal_relevance       │  Alignment with stated goals
│ )                             │
│                               │
│ Post-ranking adjustments:     │
│ ├── Diversity: max 2 per cat  │
│ ├── Position bias correction  │
│ └── Experiment override       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Select CTA + framing          │  ~5ms
│                               │
│ Template selected by:         │
│ ├── Lifecycle stage           │
│ ├── Engagement trend          │
│ └── Experiment variant        │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Return response               │  ~10ms serialization
│                               │
│ { feed: [...ranked content],  │
│   cta: {text, action},        │
│   experiments: [exposures],   │
│   flags: {evaluated_values} } │
└──────────────────────────────┘

Total: ~90ms (under 100ms budget)
```

**Graceful degradation:** If the ML model is unavailable (SageMaker timeout, model deployment failure), the system falls back to a rule-based ranking: content sorted by recency × goal relevance. Users still get a feed, just less personalized. The fallback is indistinguishable to the user — no error states, no loading spinners.

### 2.2 Engagement Scoring Engine

Computes a real-time composite engagement score (0-100) for every user. The score is the foundation for segmentation, personalization, intervention triggers, and experiment targeting.

```
Event arrives (via Segment webhook or direct API)
              │
              ▼
┌──────────────────────────────┐
│ Classify event                │
│                               │
│ meaningful_actions:           │
│ ├── content_completed         │  Weight: 1.0
│ ├── goal_action_taken         │  Weight: 1.0
│ ├── social_interaction        │  Weight: 0.8
│ ├── content_started           │  Weight: 0.5
│ └── app_opened (no action)    │  Weight: 0.1
│                               │
│ negative_signals:             │
│ ├── notification_dismissed    │  Weight: -0.2
│ ├── notification_opt_out      │  Weight: -0.5
│ └── uninstall_detected        │  Score → 0
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Update score components       │
│                               │
│ recency (30%):                │
│ ├── Last meaningful action    │
│ ├── Decay: -5 points/day of  │
│ │   inactivity                │
│ └── Cap: 100 if active today  │
│                               │
│ frequency (25%):              │
│ ├── Sessions per week         │
│ │   (trailing 14 days)        │
│ ├── 7+/week = 100             │
│ └── Linear scale to 0         │
│                               │
│ depth (20%):                  │
│ ├── Meaningful actions per    │
│ │   session (avg trailing 7d) │
│ ├── 3+ actions = 100          │
│ └── Open-only = 10            │
│                               │
│ consistency (15%):            │
│ ├── Coefficient of variation  │
│ │   of daily engagement       │
│ │   (trailing 14 days)        │
│ ├── Low variance = 100        │
│ └── High variance = 20        │
│                               │
│ progression (10%):            │
│ ├── Goal completion rate      │
│ │   vs. expected pace         │
│ ├── On track = 100            │
│ └── No progress 14d = 0       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Compute composite + detect    │
│ state changes                 │
│                               │
│ score = weighted sum           │
│                               │
│ Tier assignment:              │
│ ├── 80-100 → Tier 1 (Power)  │
│ ├── 60-79  → Tier 2 (Regular)│
│ ├── 40-59  → Tier 3 (Casual) │
│ ├── 20-39  → Tier 4 (Drifting│
│ └── 0-19   → Tier 5 (Dormant)│
│                               │
│ Alerts:                       │
│ ├── Score drop > 15 in 3 days │
│ │   → trigger intervention    │
│ └── Tier change               │
│     → log segment transition  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Write to Redis + log          │
│                               │
│ Redis: engagement:{user_id}   │
│ ├── score: 72                 │
│ ├── tier: 2                   │
│ ├── components: {...}         │
│ ├── updated_at: timestamp     │
│ └── TTL: 24 hours             │
│                               │
│ Event log: score_updated       │
│ → Segment → Snowflake          │
└──────────────────────────────┘
```

### 2.3 Experiment Engine

Manages the full lifecycle of A/B tests from assignment through analysis.

**Assignment (on every request):**

```
Client requests experiment assignment
              │
              ▼
┌──────────────────────────────┐
│ Check Redis cache             │
│ Key: exp_assign:{user}:{exp}  │
│                               │
│ Cache hit → return variant    │
│ Cache miss ↓                  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Evaluate eligibility          │
│                               │
│ ├── Experiment active?        │
│ ├── User in target segment?   │
│ ├── User in exclusion group?  │
│ ├── Mutual exclusion check    │
│ │   (no conflicting exp)      │
│ └── Rollout % check           │
└──────────────┬───────────────┘
               │
          Eligible?
          ┌────┴────┐
          │         │
         Yes        No
          │         │
          ▼         ▼
┌─────────────┐  Return null
│ Assign       │  (not in experiment)
│ variant      │
│              │
│ bucket =     │
│   hash(      │
│     user_id  │
│     + exp_id │
│   ) % 100    │
│              │
│ variant =    │
│   bucket →   │
│   variant    │
│   mapping    │
│              │
│ (deterministic: │
│  same user    │
│  always gets  │
│  same variant)│
└──────┬──────┘
       │
       ▼
┌──────────────────────────────┐
│ Cache assignment (Redis)      │
│ Log exposure event (async)    │
│ Return variant to client      │
└──────────────────────────────┘
```

**Why deterministic hashing:** A user must always see the same variant regardless of platform (iOS, Android, web) or session. Random assignment per request would cause flickering (user sees control on one visit, treatment on the next). `hash(user_id + experiment_id) % 100` is deterministic, fast, and doesn't require a database lookup on every request.

**Guardrail Monitoring:**

```
Every 6 hours (automated job):
              │
              ▼
┌──────────────────────────────┐
│ For each active experiment:   │
│                               │
│ 1. Sample Ratio Mismatch     │
│    Expected 50/50?            │
│    Actual within 1%?          │
│    If not → ALERT (broken     │
│    assignment or logging)     │
│                               │
│ 2. Guardrail metrics          │
│    For each guardrail:        │
│    Is treatment significantly │
│    WORSE than control?        │
│    If yes → AUTO-STOP         │
│    experiment + alert PM      │
│                               │
│ 3. Data quality               │
│    Exposure count growing?    │
│    Events logging correctly?  │
│    If not → ALERT (broken     │
│    instrumentation)           │
└──────────────────────────────┘
```

### 2.4 Feature Flag Engine

Separate from experiments. Flags are permanent infrastructure for progressive rollout and operational control. Experiments are temporary and measure impact.

**Evaluation flow (< 5ms):**

```
Flag evaluation request
├── flag_key: "new_home_feed_v2"
├── user_id: "abc-123"
├── user_context: {tier: 2, lifecycle: "engaged", platform: "ios"}
              │
              ▼
┌──────────────────────────────┐
│ 1. Redis lookup               │  < 1ms
│    Key: flag:{flag_key}       │
│    Contains: full flag config │
│                               │
│    Cache miss → PostgreSQL    │
│    → populate Redis (TTL 5m)  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ 2. Evaluate rules (in order)  │
│                               │
│ a. Kill switch                │  flag.killed = true → OFF
│ b. User allowlist             │  user_id in allowlist → ON
│ c. User blocklist             │  user_id in blocklist → OFF
│ d. Segment targeting          │  user in target segment → evaluate
│ e. Rollout percentage         │  hash(user_id + flag_key) % 100
│                               │     < rollout_pct → ON
│ f. Default value              │  Return default (OFF)
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ 3. Log evaluation (async)     │
│    event: flag_evaluated       │
│    data: {flag, user, value,  │
│           rule_matched}        │
│                               │
│ 4. Return value               │
│    {value: true/false/"v2",   │
│     source: "rollout_pct"}    │
└──────────────────────────────┘
```

### 2.5 Notification Optimizer

Controls what notifications users receive, when they receive them, and through which channel.

```
Intervention trigger OR scheduled notification
              │
              ▼
┌──────────────────────────────┐
│ Should we send?               │
│                               │
│ Check frequency cap:          │
│ ├── User's tier → max/week   │
│ ├── Notifications sent this   │
│ │   week already              │
│ ├── Over cap → suppress       │
│ └── Under cap → continue      │
│                               │
│ Check fatigue signals:        │
│ ├── Dismissed last 3 pushes?  │
│ │   → downgrade to email only │
│ ├── Opened 0 of last 5?      │
│ │   → reduce frequency 50%   │
│ └── Opted out of channel?     │
│     → respect preference      │
└──────────────┬───────────────┘
               │
          Send? │
          ┌────┴────┐
          │         │
         Yes    Suppress
          │     (log suppression
          │      reason for
          ▼      analysis)
┌──────────────────────────────┐
│ Select content                │
│                               │
│ Based on:                     │
│ ├── Lifecycle stage → template│
│ ├── Goal cluster → topic      │
│ ├── Engagement trend → tone   │
│ │   ├── Declining: empathetic │
│ │   ├── Stable: encouraging   │
│ │   └── Improving: celebratory│
│ └── Experiment variant        │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Select channel + timing       │
│                               │
│ Channel priority:             │
│ ├── In-app (if user active)   │
│ ├── Push (if opted in)        │
│ └── Email (always available)  │
│                               │
│ Send time:                    │
│ ├── Per-user model: predicted │
│ │   optimal hour based on     │
│ │   historical open patterns  │
│ ├── Fallback: 10am local time │
│ └── Urgent (intervention):    │
│     send immediately          │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Dispatch via OneSignal        │
│ Log: notification_sent event  │
│ Track: open/dismiss/opt-out   │
└──────────────────────────────┘
```

---

## 3. Data Flow

### 3.1 Event Pipeline

```
User action in client
        │
        ▼
Client SDK (Segment analytics.js / analytics-react-native)
├── Event: {type, user_id, properties, timestamp, context}
├── Batched: every 30 seconds or 20 events (whichever first)
        │
        ▼
Segment (CDP)
├── Identity resolution (anonymous → known user)
├── Fan-out to destinations:
│
├──→ Snowflake (warehouse)
│    ├── Raw events table (append-only)
│    ├── dbt models transform into:
│    │   ├── user_behavioral_profiles (daily aggregates)
│    │   ├── experiment_exposures (assignment + metric events)
│    │   ├── cohort_tables (segment membership over time)
│    │   └── feature_store_tables (ML training features)
│    └── Latency: < 5 minutes
│
├──→ Redis (via Segment webhook → FastAPI endpoint)
│    ├── Real-time engagement score update
│    ├── Session tracking
│    └── Latency: < 500ms
│
├──→ Amplitude (product analytics)
│    ├── Funnel analysis
│    ├── Cohort charts
│    ├── Retention curves
│    └── Latency: < 1 minute
│
└──→ OneSignal (conditional)
     ├── User property updates (for notification targeting)
     └── Latency: < 1 minute
```

### 3.2 ML Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                       ML PIPELINE                                │
│                                                                  │
│  TRAINING (daily batch, SageMaker)                               │
│                                                                  │
│  Snowflake feature tables                                        │
│       │                                                          │
│       ▼                                                          │
│  Feature Store (Feast)                                           │
│  ├── Point-in-time correct feature retrieval                     │
│  ├── Prevents training-serving skew                              │
│  └── Features: engagement_score, session_count_14d,              │
│      content_completions_7d, notification_opens_7d,              │
│      days_since_signup, goal_cluster, ...                        │
│       │                                                          │
│       ▼                                                          │
│  Model training (SageMaker)                                      │
│  ├── Churn prediction: XGBoost gradient boosting                 │
│  │   Label: churned within 14 days (binary)                      │
│  │   AUC: 0.84                                                   │
│  │                                                               │
│  ├── Content ranking: collaborative filtering (ALS)              │
│  │   User-item interaction matrix                                │
│  │   Evaluated: NDCG@10 = 0.72                                  │
│  │                                                               │
│  ├── User clustering: k-means (k=5 goal clusters)               │
│  │   Features: onboarding answers + behavioral signals           │
│  │   Silhouette score: 0.61                                      │
│  │                                                               │
│  └── Send time optimization: logistic regression                 │
│      Features: historical open times, timezone, platform         │
│      Accuracy: 68% (predicts correct 2-hour window)              │
│       │                                                          │
│       ▼                                                          │
│  Model registry (SageMaker)                                      │
│  ├── Versioned model artifacts                                   │
│  ├── A/B model comparison via experiment platform                │
│  └── Automatic rollback if performance degrades                  │
│                                                                  │
│  SERVING                                                         │
│                                                                  │
│  SageMaker endpoints (real-time inference)                       │
│  ├── Churn prediction: ~15ms per user                            │
│  ├── Content ranking: ~30ms per request (batch of candidates)    │
│  └── Send time: ~5ms per user                                    │
│                                                                  │
│  Feature Store (Feast online store → Redis)                      │
│  ├── Same features used in training served at inference           │
│  ├── No training-serving skew                                    │
│  └── Feature retrieval: ~3ms                                     │
│                                                                  │
│  MONITORING                                                      │
│                                                                  │
│  ├── Model accuracy tracked daily (compare predictions vs.       │
│  │   actual outcomes after 14-day window)                        │
│  ├── Feature drift detection (input distribution shift)          │
│  ├── Prediction distribution monitoring (output shift)           │
│  └── Alert: AUC drops > 0.05 from baseline → retrain + review   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Infrastructure

### 4.1 Deployment Architecture

| Component | Service | Rationale |
|---|---|---|
| Mobile app | App Store / Google Play | React Native, shared codebase |
| Web app | Vercel | Next.js native hosting, edge CDN |
| API servers | AWS ECS (Fargate) | Auto-scaling containers, no server management, VPC for SageMaker access |
| PostgreSQL | AWS RDS | Managed, automated backups, read replicas for experiment queries |
| Redis | AWS ElastiCache | Low-latency flag evaluation and score caching, cluster mode for high availability |
| Snowflake | Snowflake (SaaS) | Separate compute/storage, handles 500M+ events/month without performance tuning |
| ML models | AWS SageMaker | Managed training + hosting, built-in A/B endpoint testing, auto-scaling inference |
| Feature store | Feast (on Snowflake + Redis) | Offline features in Snowflake, online serving via Redis, prevents training-serving skew |
| Event pipeline | Segment | Managed CDP, handles event collection + routing + identity resolution |
| Notifications | OneSignal | Multi-channel (push, email, in-app), personalized delivery, send time optimization |
| Analytics | Amplitude | Self-serve product analytics for PMs, cohort analysis, funnel visualization |
| Monitoring | Datadog + Sentry | APM for latency tracking, error monitoring, custom dashboards for ML model health |

### 4.2 Latency Budget

Personalization is on the critical path. Every millisecond matters.

```
User opens app → Personalized feed rendered

Total budget: 300ms (perceived instant)

┌──────────────────────────────────────────────────────────────┐
│ Client rendering          │ 100ms │ React Native layout      │
├───────────────────────────┼───────┼──────────────────────────┤
│ Network round trip        │ 80ms  │ CDN + API gateway        │
├───────────────────────────┼───────┼──────────────────────────┤
│ API processing            │ 90ms  │ Personalization pipeline │
│ ├── Redis lookups         │ 5ms   │ Scores, flags, segments  │
│ ├── Candidate generation  │ 15ms  │ Content filtering        │
│ ├── ML model inference    │ 40ms  │ Content ranking          │
│ ├── Post-processing       │ 15ms  │ Diversity, dedup         │
│ └── Serialization         │ 15ms  │ JSON response            │
├───────────────────────────┼───────┼──────────────────────────┤
│ Buffer                    │ 30ms  │ Network variance         │
├───────────────────────────┼───────┼──────────────────────────┤
│ TOTAL                     │ 300ms │                          │
└──────────────────────────────────────────────────────────────┘
```

### 4.3 Security

**Data classification:**

| Data Type | Classification | Storage | Access |
|---|---|---|---|
| User PII (name, email) | Sensitive | PostgreSQL (encrypted at rest) | Auth service only |
| Behavioral events | Internal | Snowflake (anonymized user_id in most tables) | Data team + PM (read-only) |
| Engagement scores | Internal | Redis + Snowflake | API service, personalization engine |
| Experiment results | Internal | Snowflake | PM + data science |
| ML model artifacts | Internal | SageMaker model registry | ML team |
| Feature flag configs | Internal | PostgreSQL + Redis | PM (write via admin UI), all services (read) |

**Experiment data isolation:**
- Experiment results are aggregated — no individual user data in PM-facing dashboards
- Segment decomposition shows cohort-level results, not individual user behavior
- PII is never included in experiment analysis tables

---

## 5. Performance Optimization

### 5.1 Caching Strategy

| Data | Cache | TTL | Invalidation | Hit Rate |
|---|---|---|---|---|
| Feature flag configs | Redis | 5 min | On flag update (pub/sub) | 99.5% |
| Engagement scores | Redis | 24 hours | On new event (overwrite) | 98% |
| Experiment assignments | Redis | Experiment duration | On experiment stop | 99% |
| User segment memberships | Redis | 1 hour | On segment transition | 95% |
| Content catalog | Redis | 15 min | On content publish | 97% |
| ML model predictions | Not cached | N/A | Fresh on every request | N/A |

ML predictions are not cached because the input features (engagement score, recent activity) change frequently. A cached prediction from 2 hours ago may be stale if the user just completed several actions.

### 5.2 Scaling Strategy

| Load Level | DAU | Architecture |
|---|---|---|
| Current | 200K | 2 API servers, 1 Redis cluster, SageMaker single endpoint |
| 2x growth | 400K | 4 API servers (auto-scale), Redis cluster mode, SageMaker auto-scaling |
| 5x growth | 1M | API behind ALB with auto-scaling group, Redis cluster with read replicas, SageMaker multi-model endpoint |

The bottleneck at scale will be ML inference. SageMaker auto-scaling handles this to a point. Beyond 1M DAU, we'd move to pre-computed recommendations (batch scoring) with real-time re-ranking, reducing inference calls by ~80%.

---

## 6. Monitoring and Observability

### 6.1 Key Dashboards

| Dashboard | Audience | Metrics |
|---|---|---|
| Personalization Health | Engineering | API latency (p50/p95/p99), ML model latency, cache hit rates, error rates, fallback activation rate |
| Experiment Monitor | PM + Data Science | Active experiments, exposure counts, guardrail status, SRM alerts, estimated completion dates |
| Engagement Overview | Product Team | Score distribution, tier breakdown, segment sizes, churn prediction accuracy |
| Notification Performance | Growth Team | Send volume, open rates by channel, opt-out rates, frequency cap hit rates, suppression reasons |
| ML Model Health | Data Science | Prediction accuracy (AUC, NDCG), feature drift, prediction distribution, retraining status |

### 6.2 Critical Alerts

| Alert | Condition | Severity | Action |
|---|---|---|---|
| Personalization latency | p95 > 150ms (50% over budget) | Critical | Check ML model latency, Redis connectivity, candidate pool size |
| Flag evaluation latency | p95 > 10ms | Warning | Check Redis, flag config size |
| Engagement score pipeline stall | No score updates in 15 minutes | Critical | Check Segment webhook delivery, Redis write failures |
| ML model accuracy drop | AUC decreases > 0.05 | Warning | Investigate feature drift, trigger retraining |
| Experiment SRM | Assignment ratio > 1% off expected | Critical | Pause experiment, investigate assignment logic |
| Guardrail breach | Any experiment guardrail significantly worse than control | Critical | Auto-stop experiment, alert PM |
| Notification opt-out spike | Opt-out rate > 2x rolling average | Warning | Check notification frequency, content relevance |
| Fallback activation | Personalization fallback triggered | Warning | Check SageMaker endpoint health |

---

## 7. Technology Selection Rationale

| Component | Selected | Alternatives Considered | Why Selected |
|---|---|---|---|
| Event pipeline | Segment | mParticle, Rudderstack | Best integration ecosystem, identity resolution, warehouse sync reliability |
| Warehouse | Snowflake | BigQuery, Redshift | Separate compute/storage for concurrent experiment analysis, dbt ecosystem, Feast compatibility |
| ML platform | SageMaker | Vertex AI, MLflow + self-hosted | Team on AWS, managed training + hosting, built-in A/B endpoint testing |
| Feature store | Feast | Tecton, SageMaker Feature Store | Open-source, Snowflake offline store, Redis online store, no vendor lock-in |
| Notifications | OneSignal | Braze, Iterable | Cost-effective at our scale, good API for programmatic send, per-user send time optimization |
| Analytics | Amplitude | Mixpanel, Heap | Best cohort analysis and retention curves, PM self-serve, experiment analysis integration |
| Cache | ElastiCache (Redis) | DynamoDB DAX, Memcached | Sub-millisecond latency, pub/sub for flag invalidation, versatile data structures |
| API framework | FastAPI | Flask, Django REST | Async native (critical for parallel Redis + ML calls), Pydantic validation, best latency profile |
