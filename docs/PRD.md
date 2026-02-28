# Product Requirements Document: Engagement & Personalization Engine

**Author:** Jacob G, Principal Product Manager
**Last Updated:** January 2025
**Status:** Approved

---

## 1. Overview

### 1.1 Product Vision

Transform a one-size-fits-all consumer platform into an adaptive system that learns each user's behavior patterns, predicts disengagement before it happens, and personalizes every touchpoint — content, notifications, and feature exposure — to maximize long-term engagement and retention.

### 1.2 Business Context

The platform had strong top-of-funnel acquisition (100K+ new signups/month) but a retention problem: 68% of users churned within 90 days. The product team was shipping features consistently but couldn't measure impact or learn systematically. Every user got the same experience regardless of their goals, behavior, or risk of disengagement.

The business needed three things:
1. **Personalization** — adapt the experience to individual users so engagement feels relevant, not generic
2. **Prediction** — identify users at risk of churning before they disappear so the team can intervene
3. **Experimentation** — build a systematic practice of testing hypotheses so every product decision is informed by data

### 1.3 Success Criteria

| Metric | Baseline | 6-Month Target | 12-Month Target |
|---|---|---|---|
| Daily active engagement rate | 22% | 26% | 28%+ |
| 90-day retention | 32% | 42% | 50%+ |
| Churn rate (targeted at-risk cohorts) | 68% | 58% | 54% |
| Experiments shipped per quarter | 3-5 | 25+ | 50+ |
| Time from hypothesis to live test | 3-4 weeks | 1 week | 3-5 days |
| Average session duration | 4.2 min | 5.0 min | 5.5+ min |
| Revenue per user (ARPU) | $8.40/mo | $9.80/mo | $11.00+/mo |

---

## 2. Personas

### 2.1 Platform User

**"Maya" — Consumer User (Health/Wellness Context)**
- Signed up with a specific goal (lose weight, manage stress, build fitness habit)
- Motivated during first week, but engagement drops as novelty fades
- Overwhelmed by generic content that doesn't match her specific situation
- Responds well to personalized nudges but quickly opts out of irrelevant notifications
- Will stay if the product feels like it understands her; will leave if it feels like a broadcast

**Key Jobs to Be Done:**
1. Make progress toward my goal without having to figure out what to do next
2. See that the platform understands where I am and what I need right now
3. Get nudged at the right time — not too much, not too little
4. Feel a sense of momentum, even on days when I'm not highly motivated
5. Easily pick up where I left off, even after a gap

### 2.2 Growth Product Manager

**"Alex" — PM on the Engagement Team**
- Responsible for engagement and retention metrics
- Has many hypotheses about what would improve retention but no way to test them safely
- Frustrated by shipping features to 100% and hoping they work
- Wants to run multiple experiments concurrently without them interfering
- Needs to demonstrate ROI of product investments to leadership

**Key Jobs to Be Done:**
1. Design an experiment with clear hypothesis, metrics, and targeting in minutes, not days
2. Launch a test to a specific user segment without engineering deployment
3. Monitor experiment health in real time and auto-stop if something breaks
4. Get statistically rigorous results without being a statistician
5. Build a searchable repository of what we've learned from past experiments

### 2.3 Data Scientist

**"Priya" — Data Scientist Supporting Product**
- Builds ML models for churn prediction, content ranking, and user clustering
- Needs consistent feature data across training and serving (no training-serving skew)
- Wants to A/B test model variants (not just product features)
- Frustrated by ad hoc data requests; wants self-serve access to experiment results
- Needs to monitor model performance in production and detect drift

**Key Jobs to Be Done:**
1. Access consistent, well-documented features for model training
2. Deploy model updates and test them against the current production model
3. Monitor model accuracy and engagement impact in real time
4. Run offline analyses on experiment data without waiting for engineering
5. Communicate model behavior and recommendations to PMs in actionable terms

---

## 3. User Flows

### 3.1 Personalized User Experience (Consumer)

```
User opens app
      │
      ▼
System evaluates user context (< 100ms)
├── Fetch engagement score from Redis cache
├── Determine lifecycle stage (new, activated, engaged, at-risk, dormant)
├── Check active experiment assignments
├── Retrieve feature flag values
      │
      ▼
Generate personalized home feed
├── Recommendation engine ranks content
│   ├── Filter by goal cluster + lifecycle stage
│   ├── Score by collaborative filtering + content affinity
│   ├── Apply experiment variant (if in recommendation experiment)
│   └── Enforce diversity (no more than 2 items from same category)
├── Select personalized CTA
│   ├── New user: "Start your first [goal-specific] activity"
│   ├── Engaged user: "Continue your streak — day 14!"
│   ├── At-risk user: "We noticed you've been away. Here's a 5-min reset."
│   └── Dormant user: "Welcome back! Here's what's new since [last visit]."
      │
      ▼
User interacts with content
├── Events streamed to Segment (content_viewed, action_completed, etc.)
├── Engagement score updated in real time
├── Recommendation model updated (interaction fed back)
      │
      ▼
Session ends
├── Determine optimal next notification time (per-user model)
├── Select notification content based on engagement tier
├── Schedule via OneSignal
```

### 3.2 Experiment Lifecycle (PM)

```
PM creates experiment
├── Hypothesis: "Adding progress indicators to the home feed will increase
│   7-day retention by 5% for activated users"
├── Primary metric: 7-day retention
├── Guardrail metrics: session duration (must not decrease), crash rate
├── Target segment: lifecycle_stage = 'activated'
├── Variants: control (current) vs. treatment (progress indicators)
├── MDE calculation: 5% relative lift, need 12,000 users per arm
├── Estimated runtime: 18 days at current traffic
      │
      ▼
Review + approval
├── Data science reviews statistical design
├── Engineering reviews implementation (feature flag wired to UI)
├── PM confirms targeting and guardrails
      │
      ▼
Experiment starts
├── Feature flag gates the treatment
├── Progressive rollout: 5% → 20% → 50% (monitoring at each step)
├── Assignment: deterministic hash(user_id + experiment_id) % 100
├── Exposure logged on every flag evaluation
      │
      ▼
Monitoring (ongoing)
├── Dashboard: daily metric updates, cumulative lift estimate
├── Guardrail check: auto-stop if session duration drops > 10% vs. control
├── Interaction check: no other experiment running on same surface
├── Sample ratio mismatch (SRM) check: flag if assignment ratio deviates
      │
      ▼
Analysis
├── Sequential testing: can peek without inflating false positive rate
├── Primary metric: 7-day retention, treatment vs. control
├── Segment decomposition: impact by platform (iOS/Android/web), tier, cohort
├── Novelty check: does the effect persist after day 14?
├── Long-term holdout: 5% of users held out for 90-day persistent effect check
      │
      ▼
Decision
├── Ship: effect is positive, significant, persists past novelty window
├── Iterate: directionally positive but below MDE, modify and re-test
├── Kill: no effect or negative effect, document learning, move on
├── Document in experiment repository with full analysis
```

### 3.3 Proactive Intervention (Engagement Scoring)

```
User's engagement score drops below threshold
      │
      ▼
Risk detection
├── Score dropped from Tier 2 (60-79) to Tier 3 (40-59) in 3 days
├── Pattern matches "drifting" behavioral cohort
├── Churn prediction model: 72% probability of churning within 14 days
      │
      ▼
Intervention selection
├── Rule engine selects intervention based on:
│   ├── User's goal cluster (what content is most relevant)
│   ├── User's notification preferences (push? email? in-app only?)
│   ├── Past intervention history (don't repeat what didn't work)
│   └── Active experiments (is user in an intervention experiment?)
      │
      ▼
Intervention execution
├── Day 1: Personalized in-app message on next open
│   "Hey Maya, we have a new 5-minute stress reset based on your goals."
├── Day 3 (if no engagement): Push notification
│   "Your 14-day streak is at risk. Tap for a quick win to keep it going."
├── Day 7 (if still no engagement): Email with personalized content digest
│   "Here's what's new this week that matches your goals."
      │
      ▼
Track intervention outcome
├── Did user re-engage within 7 days? (success)
├── Did user engage with intervention content? (partial success)
├── Did user opt out of notifications? (negative signal — reduce frequency)
├── Feed outcome back to intervention model for future optimization
```

---

## 4. Functional Requirements

### 4.1 Personalization Service

| ID | Requirement | Priority |
|---|---|---|
| PS-01 | Generate personalized content feed based on user context (goal, lifecycle, engagement tier) | P0 |
| PS-02 | Rank content using collaborative filtering + content affinity model | P0 |
| PS-03 | Adapt CTA copy and framing based on lifecycle stage | P0 |
| PS-04 | Enforce content diversity in feed (max 2 items per category) | P1 |
| PS-05 | Dedup recently seen content (48-hour window) | P0 |
| PS-06 | Personalize notification content and copy per engagement tier | P0 |
| PS-07 | Optimize notification send time per user (learned from engagement patterns) | P1 |
| PS-08 | Support experiment overrides (variant-specific content ranking) | P0 |
| PS-09 | Return personalized feed within 100ms (p95) | P0 |
| PS-10 | Provide fallback content ranking if ML model is unavailable (graceful degradation) | P0 |

### 4.2 User Segmentation

| ID | Requirement | Priority |
|---|---|---|
| US-01 | Assign lifecycle stage in real time (new, activated, engaged, at-risk, dormant, reactivated) | P0 |
| US-02 | Assign behavioral cohort based on trailing 14-day activity (power, regular, casual, drifting, dormant, churned) | P0 |
| US-03 | Assign goal cluster via onboarding survey + behavioral signals | P0 |
| US-04 | Calculate engagement tier from composite engagement score | P0 |
| US-05 | Support custom segment definitions (PM-created rules via admin UI) | P1 |
| US-06 | Segment membership queryable via API (for experiment targeting) | P0 |
| US-07 | Segment transitions logged as events (for cohort analysis) | P1 |
| US-08 | Historical segment membership preserved (user was in segment X from date A to date B) | P1 |

### 4.3 Engagement Scoring

| ID | Requirement | Priority |
|---|---|---|
| ES-01 | Calculate composite engagement score (0-100) in real time per user | P0 |
| ES-02 | Score components: recency (30%), frequency (25%), depth (20%), consistency (15%), progression (10%) | P0 |
| ES-03 | Assign engagement tier based on score (Tier 1: 80-100 through Tier 5: 0-19) | P0 |
| ES-04 | Detect score drops exceeding threshold (>15 points in 3 days) and trigger alerts | P0 |
| ES-05 | Churn prediction model: probability of churning within 14 days | P0 |
| ES-06 | Score available via API for personalization, experiments, and downstream systems | P0 |
| ES-07 | Score history stored for trend analysis (trailing 90 days, daily granularity) | P1 |
| ES-08 | Dashboard showing score distribution across user base (for product team) | P1 |

### 4.4 Experimentation Platform

| ID | Requirement | Priority |
|---|---|---|
| EX-01 | Create experiments with hypothesis, primary metric, guardrails, targeting, and variants | P0 |
| EX-02 | Deterministic user assignment via hash (consistent across sessions and platforms) | P0 |
| EX-03 | Log exposure events on every experiment evaluation | P0 |
| EX-04 | Progressive rollout support (configurable percentage ramp) | P0 |
| EX-05 | Guardrail monitoring with auto-stop (configurable thresholds) | P0 |
| EX-06 | Sample ratio mismatch (SRM) detection and alerting | P0 |
| EX-07 | Sequential testing support (valid peeking without inflated false positives) | P1 |
| EX-08 | Segment decomposition (results by platform, cohort, tier) | P1 |
| EX-09 | Long-term holdout support (5% persistent holdout per experiment) | P1 |
| EX-10 | Experiment repository with searchable results and learnings | P1 |
| EX-11 | Mutual exclusion groups (prevent conflicting experiments on same surface) | P1 |
| EX-12 | Admin UI for experiment creation, monitoring, and analysis (PM self-serve) | P0 |
| EX-13 | Novelty effect detection (compare week 1 vs. week 3 effect size) | P2 |

### 4.5 Feature Flags

| ID | Requirement | Priority |
|---|---|---|
| FF-01 | Boolean and multivariate flag support | P0 |
| FF-02 | Percentage-based rollout (0-100%) | P0 |
| FF-03 | Segment-targeted flags (show to specific user segments only) | P0 |
| FF-04 | User allowlist/blocklist overrides | P0 |
| FF-05 | Kill switch (instant off for any flag) | P0 |
| FF-06 | Flag evaluation < 5ms (p95) via Redis cache | P0 |
| FF-07 | Evaluation audit log (who saw what flag value when) | P1 |
| FF-08 | Flag lifecycle management (created, active, stale alert at 30 days, archived) | P1 |
| FF-09 | Dependency tracking (flag X requires flag Y to be on) | P2 |

### 4.6 Notification Optimization

| ID | Requirement | Priority |
|---|---|---|
| NO-01 | Per-user optimal send time based on historical open patterns | P1 |
| NO-02 | Notification frequency capping per engagement tier (Tier 1: up to 5/week, Tier 5: max 1/week) | P0 |
| NO-03 | Content personalization based on goal cluster and lifecycle stage | P0 |
| NO-04 | Multi-channel support (push, email, in-app) with user preference respect | P0 |
| NO-05 | Intervention escalation sequence (in-app → push → email) for at-risk users | P0 |
| NO-06 | Notification A/B testing (copy, timing, channel) integrated with experiment platform | P1 |
| NO-07 | Opt-out tracking and automatic frequency reduction for users showing fatigue signals | P0 |

---

## 5. Non-Functional Requirements

| Category | Requirement | Target |
|---|---|---|
| Performance | Personalization API response time | < 100ms (p95) |
| Performance | Feature flag evaluation | < 5ms (p95) |
| Performance | Engagement score update | < 500ms from event to updated score |
| Performance | Experiment assignment | < 10ms (p95) |
| Availability | Platform uptime | 99.9% (personalization is on the critical path) |
| Scalability | Concurrent users | 200K+ DAU, 50K+ concurrent sessions |
| Scalability | Events processed | 500M+ events/month |
| Scalability | Concurrent experiments | 20+ simultaneous experiments |
| Data | Event latency (Segment → Snowflake) | < 5 minutes |
| Data | Feature store freshness | < 1 hour for batch features, real-time for streaming |
| Security | PII handling | User behavioral data anonymized in warehouse; PII in PostgreSQL only |
| Security | Experiment data | Results accessible only to PM + data science roles |

---

## 6. Out of Scope (V1)

| Feature | Reason | Revisit When |
|---|---|---|
| Multi-armed bandits | Need stable experiment framework first; bandits are optimization, not learning | Experiment velocity > 50/quarter and team is comfortable with frequentist testing |
| Causal inference (observational studies) | Requires sophisticated data science tooling; start with controlled experiments | Data science team grows to 3+ and requests tooling |
| Real-time ML model retraining | Batch retraining (daily) sufficient for V1 engagement patterns | If engagement patterns shift faster than daily (e.g., live events, trending content) |
| Cross-device experiment assignment | Start with user-level assignment; cross-device adds identity complexity | Identity resolution is robust and cross-device usage exceeds 30% |
| Natural language content generation | Personalized copy via templates in V1; GenAI content later | Template library becomes bottleneck for personalization variants |
| Third-party data enrichment | Start with first-party behavioral data only | First-party signals plateau in predictive power |

---

## 7. Appendix

### 7.1 Engagement Score Components

| Component | Weight | Signal | Score = 100 | Score = 0 |
|---|---|---|---|---|
| Recency | 30% | Time since last meaningful action | Active today | 14+ days ago |
| Frequency | 25% | Sessions per week (trailing 14 days) | 7+ sessions/week | 0 sessions in 14 days |
| Depth | 20% | Meaningful actions per session (not just opens) | 3+ actions/session | Open-only, no actions |
| Consistency | 15% | Standard deviation of daily engagement | Engages same days/times weekly | Highly irregular |
| Progression | 10% | Movement toward stated goal | On track or ahead | No progress in 14 days |

### 7.2 Notification Frequency by Engagement Tier

| Tier | Score Range | Max Notifications/Week | Channels |
|---|---|---|---|
| Tier 1 (Power) | 80-100 | 5 | Push, email, in-app |
| Tier 2 (Regular) | 60-79 | 4 | Push, email, in-app |
| Tier 3 (Casual) | 40-59 | 3 | Push, email |
| Tier 4 (Drifting) | 20-39 | 2 | Push (gentle), email |
| Tier 5 (Dormant) | 0-19 | 1 | Email only (re-engagement) |

### 7.3 Experiment Sizing Reference

| Effect Size (Relative) | Users Per Arm (80% power, α=0.05) | Approximate Runtime (at 10K DAU) |
|---|---|---|
| 1% | 1,570,000 | Not feasible — need proxy metric |
| 2% | 393,000 | ~80 days |
| 5% | 63,000 | ~13 days |
| 10% | 16,000 | ~4 days |
| 20% | 4,000 | ~1 day |

Rule of thumb: if you need > 30 days to detect the expected effect, find a more sensitive metric or accept that this experiment isn't worth running.
