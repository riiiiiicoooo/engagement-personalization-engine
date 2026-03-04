# Engagement & Personalization Engine

A consumer platform personalization system combining ML-powered recommendations, real-time user segmentation, and a rigorous experimentation framework to drive engagement, retention, and monetization. Built for a consumer wellness platform serving 2M+ weekly active users managing ongoing health and lifestyle goals.

The architecture generalizes to any consumer product where engagement is the business: health apps, fintech, e-commerce, media, education, social.

---

## The Problem

The platform had strong acquisition but poor retention. Users signed up, engaged for 2-3 weeks, then dropped off. The product treated every user the same, same onboarding, same content, same notification cadence, regardless of their goals, behavior patterns, or risk of disengagement.

**For users:**
- Generic experience that didn't adapt to individual goals or progress
- Content and recommendations irrelevant to their specific situation
- Notification fatigue from one-size-fits-all messaging
- No sense of progress or momentum to sustain long-term engagement

**For the business:**
- 68% of users churned within 90 days of signup
- No systematic way to identify at-risk users before they disappeared
- Product decisions made by intuition, not data, ther was no experimentation culture
- Feature launches were all-or-nothing: ship to 100% and hope
- Engagement metrics flat despite continuous feature investment

**For the product team:**
- No framework to prioritize growth investments (what moves retention vs. what doesn't?)
- No way to safely test risky ideas without endangering core metrics
- User research surfaced qualitative themes but couldn't quantify impact
- Engineering velocity was high but business impact was unclear

---

## The Solution

Three interconnected systems that make the product smarter as usage scales:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PERSONALIZATION ENGINE                                │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ User Segmentation │  │ Recommendation   │  │ Engagement Scoring   │  │
│  │                   │  │ Engine           │  │                      │  │
│  │ Behavioral cohorts│  │ Content ranking  │  │ Real-time health     │  │
│  │ Lifecycle stage   │  │ Journey adaption │  │ score per user       │  │
│  │ Goal clustering   │  │ Notification     │  │ Churn prediction     │  │
│  │ Risk profiling    │  │ personalization  │  │ Intervention         │  │
│  │                   │  │                  │  │ triggers             │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘  │
│           │                      │                        │             │
│           └──────────────────────┼────────────────────────┘             │
│                                  │                                      │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    EXPERIMENTATION PLATFORM                              │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ A/B Testing      │  │ Feature Flags    │  │ Analysis Engine      │  │
│  │                   │  │                  │  │                      │  │
│  │ Hypothesis-driven │  │ Progressive      │  │ Statistical rigor    │  │
│  │ experiment design │  │ rollout (1% →    │  │ (sequential testing, │  │
│  │ Segment targeting │  │ 10% → 50% →     │  │ MDE calculation,     │  │
│  │ Guardrail metrics │  │ 100%)            │  │ novelty detection)   │  │
│  │ Auto-stop rules   │  │ Kill switch      │  │ Metric decomposition │  │
│  │                   │  │ Audience gates    │  │ Long-term holdouts   │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    DATA PLATFORM                                         │
│                                                                          │
│  Event Stream (Segment)  →  Warehouse (Snowflake)  →  Feature Store     │
│  User profiles              Behavioral aggregates      ML model inputs   │
│  Session events             Cohort tables               Real-time scores │
│  Conversion events          Experiment results          Segment membership│
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Results

| Metric | Before | After | Impact |
|---|---|---|---|
| Daily active engagement rate | 22% | 28.2% | +28% lift |
| Average session duration | 4.2 min | 5.7 min | +35% increase |
| 90-day retention | 32% | 51% | +59% improvement |
| Churn rate (targeted cohorts) | 68% at 90 days | 54% at 90 days | 20% reduction |
| Notification opt-out rate | 34% | 18% | 47% reduction |
| Experiments run per quarter | 3-5 (ad hoc) | 50+ (systematic) | 10x velocity |
| Time from hypothesis to live test | 3-4 weeks | 3-5 days | 80% faster |
| Feature rollout incidents | ~2/quarter | 0 in last 6 months | Eliminated |
| Revenue per user (ARPU) | $8.40/mo | $11.20/mo | +33% lift |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       CLIENT LAYER                                       │
│                                                                          │
│  Mobile App (React Native)          Web App (Next.js)                   │
│  ├── Personalized home feed          ├── Dashboard with recommendations  │
│  ├── Adaptive content delivery       ├── Progress tracking               │
│  ├── Smart notifications             ├── Goal management                 │
│  └── Feature flag evaluation         └── Feature flag evaluation         │
│                                                                          │
│  SDK: Experiment assignment, event tracking, flag evaluation (client)    │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       API LAYER (FastAPI)                                 │
│                                                                          │
│  /api/v1/personalize    - Get personalized content for user              │
│  /api/v1/recommend      - Content/action recommendations                 │
│  /api/v1/experiments    - Experiment assignment + exposure logging        │
│  /api/v1/flags          - Feature flag evaluation                        │
│  /api/v1/segments       - User segment membership                        │
│  /api/v1/engagement     - Engagement score + health indicators           │
│  /api/v1/events         - Event ingestion (client → server)              │
│  /api/v1/admin          - Experiment management, flag config, segments   │
└──────────┬──────────────┬──────────────┬──────────────┬─────────────────┘
           │              │              │              │
           ▼              ▼              ▼              ▼
┌──────────────┐ ┌────────────────┐ ┌────────────┐ ┌──────────────────┐
│ Personali-   │ │ Experiment     │ │ Feature    │ │ Engagement       │
│ zation       │ │ Service        │ │ Flag       │ │ Scoring          │
│ Service      │ │                │ │ Service    │ │ Service          │
│              │ │ Assignment     │ │            │ │                  │
│ User model   │ │ Bucketing      │ │ Flag eval  │ │ Real-time score  │
│ Content rank │ │ Exposure log   │ │ Rollout %  │ │ Churn prediction │
│ Journey      │ │ Guardrails     │ │ Targeting  │ │ Risk segments    │
│ adaptation   │ │ Auto-stop      │ │ Kill switch│ │ Intervention     │
│ Notification │ │ Results        │ │ Audit log  │ │ triggers         │
│ optimization │ │ analysis       │ │            │ │                  │
└──────────────┘ └────────────────┘ └────────────┘ └──────────────────┘
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
│  │ Experiments config │  │ Feature flags│  │ Event warehouse          │ │
│  │ Flag definitions   │  │ (fast eval)  │  │ User behavioral profiles │ │
│  │ Segment rules      │  │ Engagement   │  │ Experiment results       │ │
│  │ User profiles      │  │ scores cache │  │ Cohort tables            │ │
│  │ Assignments        │  │ Session data │  │ ML training data         │ │
│  └───────────────────┘  └──────────────┘  └──────────────────────────┘ │
│                                                                          │
│  ┌───────────────────┐  ┌──────────────────────────────────────────┐   │
│  │ Segment (CDP)      │  │ ML Models (SageMaker)                    │   │
│  │                    │  │                                          │   │
│  │ Event streaming    │  │ Churn prediction (gradient boosting)     │   │
│  │ Identity resolution│  │ Content ranking (collaborative filter)   │   │
│  │ Real-time profiles │  │ Engagement scoring (regression)          │   │
│  │ Warehouse sync     │  │ User clustering (k-means)               │   │
│  └───────────────────┘  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Modern Stack

**Phase 1 → Phase 2 Evolution**: The original system built experimentation and personalization infrastructure from scratch, demonstrating deep understanding of the mechanics. Phase 2 migrated core components to industry-standard platforms—showing judgment in build-vs-buy decisions and operational maturity.

> "Building it first taught us the constraints. Migrating to PostHog/Supabase/n8n demonstrates we know what good looks like and can execute at scale."

### Phase 2 Tech Stack (Current)

| Layer | Technology | Rationale | Phase 1 Alternative |
|---|---|---|---|
| **Frontend** | Next.js 14 + TypeScript | SSR for SEO, fast iteration, unified codebase | Next.js + custom state |
| **Backend** | Node.js/TypeScript + FastAPI | Type-safe APIs, async event processing | Python-only FastAPI |
| **Primary DB** | Supabase (PostgreSQL + RLS) | Real-time capabilities, RLS for multi-tenant safety, managed ops | Self-hosted PostgreSQL |
| **Feature Flags** | PostHog | Built-in experiment platform, statistical rigor, real-time rollout | Custom flag service |
| **Experimentation** | PostHog + TypeScript SDK | Sequential testing, guardrail metrics, segment targeting | Custom experiment framework |
| **Workflows** | n8n (self-hosted or cloud) | Visual workflow builder, Supabase + Resend integrations, webhook triggers | Custom Python scripts |
| **Background Jobs** | Trigger.dev | Reliable job scheduling, checkpointing for large batches, built-in retry logic | Celery + Redis |
| **Email** | Resend + React Email | Type-safe email templates, transactional reliability | SendGrid templates |
| **Analytics** | PostHog (cohort analysis) | Product-native analytics, integrated with feature flags | Amplitude (separate) |
| **Caching** | Redis (optional) | Feature flag evaluation, engagement score cache | Built-in PostgreSQL cache |
| **Monitoring** | Vercel Analytics + PostHog | Real User Monitoring, integrated platform insights | Datadog (separate) |

### Quick Start

```bash
# Install dependencies
npm install

# Setup local Supabase (optional)
npm run db:start

# Run migrations
npm run db:migrate

# Start development server
npm run dev

# Run background jobs (Trigger.dev local)
npx trigger.dev@latest dev
```

### Configuration

See [.env.example](.env.example) for all environment variables.

Key services to configure:
1. **Supabase**: Create project, run migrations from `supabase/migrations/001_initial_schema.sql`
2. **PostHog**: Create project, copy API key to `.env.local`
3. **Resend**: Get API key for transactional emails
4. **Trigger.dev**: Connect backend job server (free tier available)
5. **n8n**: Deploy workflows for notification orchestration and cohort recalculation

---

## Phase 1: Original Tech Stack (Reference)

| Layer | Technology | Rationale |
|---|---|---|
| Mobile | React Native | Cross-platform, shared experiment SDK, fast iteration |
| Web | Next.js 14 | SSR for SEO, shared component library with admin dashboard |
| API | FastAPI (Python) | Low-latency personalization serving, native async, ML model integration |
| Primary DB | PostgreSQL | Experiment configs, flag definitions, segment rules, user profiles |
| Cache | Redis | Feature flag evaluation (<5ms), engagement score cache, session state |
| Warehouse | Snowflake | Event storage, behavioral aggregates, experiment analysis, ML training data |
| CDP | Segment | Event collection, identity resolution, real-time user profiles, warehouse sync |
| ML Platform | AWS SageMaker | Model training, hosting, A/B model comparison, batch inference |
| Feature Store | Feast (on Snowflake) | Consistent feature serving for ML models (training and inference) |
| Notifications | OneSignal | Multi-channel (push, email, in-app), personalized delivery timing |
| Analytics | Amplitude | Product analytics, funnel analysis, cohort tracking, experiment analysis |
| Monitoring | Datadog + Sentry | APM for personalization latency, error tracking, ML model drift alerts |

---

## Key Design Decisions

| Decision | Choice | Alternative | Why |
|---|---|---|---|
| Real-time engagement scoring | Compute score on every session, cache in Redis | Batch scoring (daily) | Users can shift from healthy to at-risk in a single session. Batch scoring misses fast deterioration. |
| Server-side experiment assignment | API assigns experiments on request | Client-side (Optimizely, LaunchDarkly) | Full control over assignment logic, no client SDK dependency, consistent cross-platform behavior |
| Snowflake for experiment analysis | Run analysis in warehouse | In-app analytics tool | Statistical rigor requires raw event access. Pre-built tools lack sequential testing and custom metric decomposition. |
| Collaborative filtering for recommendations | User-item interaction matrix | Content-based only | Collaborative filtering captures "users like you also engaged with X" patterns that content-based misses |
| Feature flags separate from experiments | Flags for rollout, experiments for measurement | Combined system | Different lifecycles: flags are permanent infrastructure, experiments are temporary. Combining creates operational confusion. |
| Engagement score as composite | Weighted multi-signal score (0-100) | Single metric (DAU/MAU) | DAU/MAU is too coarse. A user who opens the app daily but never completes meaningful actions looks "engaged" but isn't. |
| Progressive rollout (1→10→50→100%) | Gradual rollout with monitoring at each stage | Ship to 100% with kill switch | Two rollout incidents in early months taught us that gradual rollout catches issues before they affect the full user base |

---

## System Components

### 1. User Segmentation

Users are segmented along four dimensions that update in real time:

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER SEGMENT MODEL                            │
│                                                                  │
│  LIFECYCLE STAGE              BEHAVIORAL COHORT                  │
│  ├── New (days 0-7)           ├── Power users (daily, deep)     │
│  ├── Activated (completed     ├── Regular (3-5x/week)           │
│  │   first key action)        ├── Casual (1-2x/week)            │
│  ├── Engaged (sustained       ├── Drifting (was regular, now    │
│  │   activity 2+ weeks)       │   declining)                    │
│  ├── At-risk (engagement      ├── Dormant (no activity 14+ days)│
│  │   score declining)         └── Churned (no activity 30+ days)│
│  ├── Dormant (14+ days idle)                                    │
│  └── Reactivated (returned                                      │
│      after dormancy)          GOAL CLUSTER                      │
│                               ├── Cluster A (weight management) │
│  ENGAGEMENT TIER              ├── Cluster B (fitness)           │
│  ├── Tier 1: Score 80-100     ├── Cluster C (mental wellness)   │
│  ├── Tier 2: Score 60-79      ├── Cluster D (chronic condition) │
│  ├── Tier 3: Score 40-59      └── Cluster E (general wellness)  │
│  ├── Tier 4: Score 20-39                                        │
│  └── Tier 5: Score 0-19                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Engagement Scoring

A real-time composite score (0-100) that captures how engaged a user is *right now*, not just historically.

```
engagement_score = (
    0.30 × recency_score +        # How recently they were active
    0.25 × frequency_score +      # How often they engage (trailing 14 days)
    0.20 × depth_score +          # Quality of engagement (actions, not just opens)
    0.15 × consistency_score +    # Regularity of engagement pattern
    0.10 × progression_score      # Movement toward their stated goals
)
```

### 3. Recommendation Engine

Ranks and personalizes content, actions, and notifications for each user.

```
User opens app
      │
      ▼
Fetch user context
├── Engagement score + tier
├── Lifecycle stage
├── Goal cluster
├── Recent activity (last 7 days)
├── Content interaction history
├── Active experiment assignments
      │
      ▼
Generate candidates
├── Content pool (articles, programs, activities)
├── Filter by relevance (goal cluster, lifecycle stage)
├── Remove recently seen (dedup window: 48 hours)
      │
      ▼
Rank candidates
├── Collaborative filtering score (users like you engaged with X)
├── Content-user affinity score (past interaction patterns)
├── Freshness boost (new content gets temporary lift)
├── Diversity penalty (don't show 5 articles on same topic)
├── Engagement tier adjustment (Tier 4-5 get simpler, lower-barrier content)
      │
      ▼
Apply experiment overrides
├── If user in recommendation experiment, apply variant logic
├── Log exposure event for analysis
      │
      ▼
Return personalized feed
├── Ranked content list
├── Personalized CTA copy (varies by lifecycle stage)
├── Notification schedule (optimized send time per user)
```

### 4. Experimentation Platform

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXPERIMENT LIFECYCLE                           │
│                                                                  │
│  DESIGN                                                          │
│  ├── Hypothesis: "Changing X will improve Y by Z%"              │
│  ├── Primary metric + guardrail metrics                          │
│  ├── Minimum detectable effect (MDE) calculation                 │
│  ├── Required sample size → estimated runtime                    │
│  ├── Targeting rules (segment, lifecycle, platform)              │
│  └── Review + approval (PM + data science)                       │
│                                                                  │
│  EXECUTION                                                       │
│  ├── Assignment: deterministic hashing (user_id + experiment_id) │
│  ├── Exposure logging: every flag evaluation logged              │
│  ├── Guardrail monitoring: auto-stop if guardrail breached       │
│  ├── Progressive rollout: 5% → 20% → 50% → 100%                │
│  └── Runtime: sequential testing with spending functions          │
│                                                                  │
│  ANALYSIS                                                        │
│  ├── Primary metric: frequentist + Bayesian credible intervals   │
│  ├── Segment decomposition: impact by cohort, platform, tier     │
│  ├── Novelty detection: check if effect decays after 2 weeks     │
│  ├── Long-term holdout: 5% holdout for persistent effect check   │
│  └── Decision: ship, iterate, or kill (documented with reasoning)│
│                                                                  │
│  LEARNING                                                        │
│  ├── Result logged in experiment repository                      │
│  ├── Insight shared in weekly product review                     │
│  └── Feeds into next hypothesis generation                       │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Feature Flags

```
Flag evaluation flow (< 5ms target):

Client requests flag value
        │
        ▼
┌─────────────────────┐
│ Check Redis cache    │  Cache hit → return value (< 1ms)
│                      │  Cache miss ↓
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Evaluate flag rules  │
│                      │
│ 1. Kill switch?      │  If killed → return default (off)
│ 2. User allowlist?   │  If in allowlist → return override value
│ 3. Segment targeting?│  If user in target segment → evaluate
│ 4. Rollout %?        │  Hash(user_id + flag_id) < rollout% → on
│ 5. Default           │  Return default value
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Cache result (Redis) │  TTL: 5 minutes
│ Log evaluation event │  Async → event stream
│ Return value         │
└─────────────────────┘
```

---

## Repository Structure

```
engagement-personalization-engine/
├── README.md
├── docs/
│   ├── PRD.md                         # Product requirements
│   ├── ARCHITECTURE.md                # System design and data flow
│   ├── DATA_MODEL.md                  # Schema, feature store, event model
│   ├── EXPERIMENTATION_GUIDE.md       # How to design, run, and analyze experiments
│   ├── PERSONALIZATION_FRAMEWORK.md   # Segmentation, scoring, recommendation logic
│   ├── METRICS.md                     # North star, growth model, guardrails
│   ├── DECISION_LOG.md                # Key technical and product decisions
│   └── ROADMAP.md                     # Phased rollout plan
└── src/
    ├── README.md                      # PM reference implementation notes
    ├── segmentation/
    │   └── user_segmenter.py          # Real-time user segmentation engine
    ├── scoring/
    │   └── engagement_scorer.py       # Composite engagement score calculator
    ├── recommendations/
    │   └── recommendation_engine.py   # Content ranking and personalization
    ├── experiments/
    │   └── experiment_framework.py    # A/B test assignment, exposure, analysis
    └── flags/
        └── feature_flags.py           # Feature flag evaluation and rollout
```

---

## Product Documents

| Document | Description |
|---|---|
| [Product Requirements](docs/PRD.md) | Personas, user flows, functional requirements, phased rollout |
| [System Architecture](docs/ARCHITECTURE.md) | Service design, data flow, ML pipeline, infrastructure |
| [Data Model](docs/DATA_MODEL.md) | Schema, event taxonomy, feature store, experiment assignments |
| [Experimentation Guide](docs/EXPERIMENTATION_GUIDE.md) | Experiment design, statistical methods, guardrails, analysis playbook |
| [Personalization Framework](docs/PERSONALIZATION_FRAMEWORK.md) | Segmentation model, engagement scoring, recommendation algorithms, notification optimization |
| [Metrics Framework](docs/METRICS.md) | North star, growth model, input metrics, guardrails |
| [Decision Log](docs/DECISION_LOG.md) | Key technical and product trade-offs with reasoning |
| [Product Roadmap](docs/ROADMAP.md) | Phased rollout from instrumentation to ML-powered personalization |

---

## Engagement & Budget

### Team & Timeline

| Role | Allocation | Duration |
|------|-----------|----------|
| Lead PM (Jacob) | 20 hrs/week | 14 weeks |
| Lead Developer (US) | 40 hrs/week | 14 weeks |
| Offshore Developer(s) | 2 × 35 hrs/week | 14 weeks |
| QA Engineer | 20 hrs/week | 14 weeks |

**Timeline:** 14 weeks total across 3 phases
- **Phase 1: Discovery & Design** (3 weeks) — User segmentation analysis, engagement model design, experimentation framework, Segment/PostHog integration mapping
- **Phase 2: Core Build** (8 weeks) — Scoring engine, recommendation service, real-time segmentation, A/B testing framework, dashboard
- **Phase 3: Integration & Launch** (3 weeks) — PostHog/Segment integration, experiment calibration, QA, staged rollout to 10% → 50% → 100% of users

### Budget Summary

| Category | Cost | Notes |
|----------|------|-------|
| PM & Strategy | $51,800 | Discovery, specs, stakeholder management |
| Development (Lead + Offshore) | $136,500 | Core platform build |
| QA | $9,800 | Quality assurance and testing |
| AI/LLM Token Budget | $350/month | Claude Haiku for engagement scoring, recommendation generation ~4M tokens/month |
| Infrastructure | $420/month | Supabase $25 + Redis $65 + Vercel $20 + Trigger.dev $25 + n8n $50 + AWS compute $150 + misc $85 |
| **Total Engagement** | **$200,000** | Fixed-price, phases billed at milestones |
| **Ongoing Run Rate** | **$900/month** | Infrastructure + AI tokens + support |
