# Product Roadmap: Engagement & Personalization Engine

**Last Updated:** January 2025

---

## Roadmap Overview

```
Phase 0: Instrument     Phase 1: Experiment     Phase 2: Personalize    Phase 3: Predict
(Weeks 1-6)             (Weeks 7-14)            (Weeks 15-22)           (Weeks 23+)

Build event pipeline    Ship experimentation    Ship personalization    ML-powered features
and scoring foundation  platform + feature      engine + notification   and advanced
                        flags                   optimization            experimentation

├─ Event taxonomy       ├─ Experiment creation  ├─ Recommendation       ├─ Churn prediction
├─ Segment SDK          │  + assignment         │  engine (collab       │  model (XGBoost)
│  integration          ├─ Feature flag         │  filtering)           ├─ Demand forecasting
├─ Engagement score     │  service              ├─ Personalized feed    ├─ Multi-armed bandits
│  (real-time)          ├─ Exposure logging     ├─ Notification         ├─ Dynamic content
├─ User segmentation    ├─ Guardrail monitoring │  optimization         │  generation
├─ Snowflake warehouse  ├─ PM admin dashboard   ├─ Intervention system  ├─ Cross-device
│  + dbt models         ├─ Progressive rollout  ├─ Tier-based frequency │  identity
├─ Redis caching layer  ├─ Analysis pipeline    │  capping              ├─ Causal inference
└─ Baseline metrics     └─ 10 experiments       ├─ Cold start handling  │  tooling
                            shipped              └─ Feast feature store  └─ Real-time model
                                                                            retraining
```

---

## Phase 0: Instrument (Weeks 1-6)

**Goal:** Build the data foundation. Before we can personalize or experiment, we need to know who our users are and what they're doing.

**Theme:** Can we measure engagement with enough granularity to act on it?

| Week | Deliverable | Details |
|---|---|---|
| 1-2 | Event taxonomy + Segment integration | Define all events (see Data Model event catalog). Integrate Segment SDK into iOS, Android, and web apps. Validate event delivery end-to-end. |
| 2-3 | Snowflake warehouse + dbt models | Configure Segment → Snowflake pipeline. Build dbt models: raw_events → user_behavioral_profiles → cohort_retention. Validate data quality. |
| 3-4 | Engagement scoring engine | Build real-time scoring service. Components: recency, frequency, depth, consistency, progression. Redis caching. Score update on every meaningful event. |
| 4-5 | User segmentation engine | Implement four segmentation dimensions: lifecycle stage, behavioral cohort, engagement tier, goal cluster. Real-time segment assignment. Segment membership API. |
| 5-6 | Baseline measurement + dashboards | Establish baseline for all input metrics (retention, engagement rate, session duration). Build Amplitude dashboards. Measure current engagement score distribution. |

**Exit Criteria:**
- All defined events flowing through Segment → Snowflake with < 5 minute latency
- Engagement scores computing in real-time for 100% of active users
- Score distribution dashboard live and showing all five tiers
- Baseline metrics documented for pre/post comparison
- User segmentation operational across all four dimensions
- dbt models running daily with < 2% data quality errors

**Key Risks:**
- Event taxonomy gaps. Mitigation: instrument core events first (session, content, notification), add secondary events in Phase 1.
- Segment SDK increases app bundle size. Mitigation: measured at 180KB — acceptable.

---

## Phase 1: Experiment (Weeks 7-14)

**Goal:** Ship the experimentation platform and feature flag service. Run 10 real experiments to validate the system and start building experimentation culture.

**Theme:** Can we safely test ideas and learn from the results?

| Week | Deliverable | Details |
|---|---|---|
| 7-8 | Experiment assignment engine | Deterministic hash-based assignment. Segment targeting. Mutual exclusion groups. Redis caching of assignments. |
| 8-9 | Feature flag service | Flag definition (boolean + multivariate). Percentage rollout. Segment targeting. Kill switch. Redis-cached evaluation (< 5ms). Evaluation audit log. |
| 9-10 | Exposure logging + guardrails | Exposure event logging on every flag evaluation. Guardrail monitoring (6-hour checks). Auto-stop on guardrail breach. SRM detection. |
| 10-11 | PM admin dashboard | Create experiment UI (hypothesis, metrics, targeting, variants). Create flag UI (rollout %, targeting, kill switch). Experiment status monitoring. |
| 11-12 | Analysis pipeline | dbt models for experiment results. Sequential testing (O'Brien-Fleming). Bayesian credible intervals. Segment decomposition. Novelty detection. |
| 12-13 | Progressive rollout + safety | Rollout ramp: 5% → 20% → 50%. Monitoring at each step. Circuit breaker: auto-fallback to control if assignment service fails. |
| 13-14 | First experiments | Run 10 experiments across home feed, notifications, and onboarding. Validate full lifecycle: design → launch → monitor → analyze → decide. |

**Exit Criteria:**
- 10 experiments completed with statistically valid results
- Feature flag evaluation < 5ms (p95)
- Experiment assignment < 10ms (p95)
- No SRM incidents in first 10 experiments
- PM admin dashboard operational (PMs can create experiments without engineering deploys)
- At least 1 experiment auto-stopped by guardrail (proving safety system works)
- Experiment repository seeded with 10 documented results

**Key Risks:**
- First experiments may have instrumentation bugs (wrong events, missing exposures). Mitigation: dry-run each experiment for 24 hours at 1% before ramping.
- PMs may not have enough hypotheses to fill 10 experiments. Mitigation: pre-build hypothesis backlog from user research, support ticket analysis, and competitive analysis.

---

## Phase 2: Personalize (Weeks 15-22)

**Goal:** Ship the personalization engine. Make the product adaptive — different users see different content, notifications, and CTAs based on who they are and how they're engaging.

**Theme:** Can we show each user what they need to see next?

| Week | Deliverable | Details |
|---|---|---|
| 15-16 | Recommendation engine (V1) | Content ranking using content affinity + goal relevance + freshness + engagement tier adjustment. Rule-based (no ML yet). Diversity enforcement. Fallback ranking. |
| 16-17 | Personalized feed | Integrate recommendation engine with home feed. Personalized CTAs by lifecycle stage. Content dedup (48-hour window). A/B test personalized vs. popularity-based feed. |
| 17-18 | Feast feature store | Set up Feast with Snowflake offline store + Redis online store. Migrate all ML features to Feast. Validate training-serving consistency. |
| 18-19 | Collaborative filtering model | Train ALS model on user-item interactions. Integrate into recommendation engine (40% weight). Cold start handling for new users and new content. |
| 19-20 | Notification optimization | Per-user send time model (logistic regression). Tier-based frequency capping. Channel selection (push, email, in-app). Fatigue detection. |
| 20-21 | Intervention system | At-risk detection from engagement score. Graduated escalation (in-app → push → email → final email). Outcome tracking. Intervention A/B testing. |
| 21-22 | Integration + tuning | End-to-end testing. Latency optimization (target: < 100ms p95). Personalization A/B test vs. non-personalized baseline. Score → intervention → outcome analysis. |

**Exit Criteria:**
- Personalized feed A/B test shows significant lift in content completion rate (target: +30% vs. baseline)
- Recommendation engine serving within 100ms (p95)
- Notification opt-out rate decreases by 10+ percentage points (from 34% baseline)
- Intervention system operational with > 30% re-engagement rate
- Feast feature store eliminating training-serving skew (AUC gap < 0.02)
- Collaborative filtering model achieving NDCG@10 > 0.65
- Graceful degradation tested: all fallbacks functional

**Key Risks:**
- Collaborative filtering cold start may produce poor recommendations for new users. Mitigation: hybrid approach — rule-based for days 0-14, collaborative filtering introduced gradually.
- Personalization latency may exceed budget. Mitigation: pre-compute candidate pool for top segments; cache ML model outputs for 5 minutes for returning sessions.

---

## Phase 3: Predict (Weeks 23+)

**Goal:** Use accumulated data and validated ML pipeline to build predictive features. Graduate from reactive (score drops → intervene) to proactive (predict who will disengage before it happens).

**Theme:** Can the platform get smarter over time?

| Deliverable | Details | Priority |
|---|---|---|
| Churn prediction model | XGBoost on Feast features. Predict 14-day churn probability. Trigger interventions at > 70% probability. Target AUC: 0.85. | P0 |
| Proactive intervention | Intervene based on churn prediction, not just score decline. Catch users before behavioral signals appear. | P0 |
| Model A/B testing | Test model versions as experiments. New model vs. current model, measured by intervention success rate. | P0 |
| Advanced experiment analysis | Causal inference for observational studies. Heterogeneous treatment effects. Automated experiment sizing recommendations. | P1 |
| Dynamic content matching | Real-time content difficulty adjustment. If user struggles with current content, automatically suggest easier alternatives. | P1 |
| Send time optimization V2 | Reinforcement learning for notification timing. Adapts per-user optimal time based on ongoing feedback (not just historical). | P1 |
| Multi-armed bandits | For low-stakes decisions (notification copy, CTA color). Automatically allocate traffic to winning variants without formal experiment lifecycle. | P2 |
| Cross-device identity | Unified user profile across devices. Consistent experiment assignment and personalization when user switches between phone and laptop. | P2 |
| Real-time model retraining | Move from daily batch to streaming model updates. Models adapt within hours, not days, to behavioral shifts. | P2 |
| Content generation | LLM-generated personalized notification copy and CTA text. Move from template library to dynamic generation. | P3 |

---

## Dependencies and Sequencing

```
Phase 0                     Phase 1                     Phase 2
────────                    ────────                    ────────
Event taxonomy ────────────► Exposure logging             Feast feature store
       │                         │                            │
       ▼                         ▼                            ▼
Segment integration ───────► Experiment assignment ─────► A/B test personalization
       │                         │                            │
       ▼                         ▼                            ▼
Engagement scoring ────────► Guardrail monitoring ──────► Intervention system
       │                         │                            │
       ▼                         ▼                            ▼
User segmentation ─────────► Feature flags ─────────────► Personalized feed
       │                         │                            │
       ▼                         ▼                            ▼
Snowflake + dbt ───────────► Analysis pipeline ─────────► Collaborative filtering
       │                         │                            │
       ▼                         ▼                            ▼
Baseline metrics ──────────► First 10 experiments ──────► Notification optimization
```

**Critical path:** Event taxonomy → Engagement scoring → User segmentation → Feature flags → Experiment assignment → Personalized feed

---

## Success Milestones

| Milestone | Target Date | Success Criteria |
|---|---|---|
| **Data flowing** | Week 3 | All core events in Snowflake, < 5 min latency |
| **Scores live** | Week 5 | Real-time engagement scores for 100% of active users |
| **First experiment shipped** | Week 10 | One experiment with valid result and documented decision |
| **10 experiments completed** | Week 14 | Full experiment lifecycle validated, repository seeded |
| **Personalization live** | Week 18 | Personalized feed showing significant lift vs. control |
| **Interventions working** | Week 21 | > 30% re-engagement rate for at-risk users |
| **Full system operational** | Week 22 | All components integrated, < 100ms latency, graceful degradation |
| **Churn prediction live** | Week 26 | Model AUC > 0.80, proactive interventions firing |
| **50 experiments/quarter** | Week 30 | Experimentation culture established, compound learning visible |

---

## What We're NOT Building (and Why)

| Feature | Why Not | Revisit When |
|---|---|---|
| Visual experiment editor (WYSIWYG) | All our experiments require code changes (feature flags). A visual editor would only handle superficial changes (button color, copy). Not worth the investment. | > 50% of experiments are purely visual (unlikely given our product) |
| Multi-armed bandits (V1) | Bandits optimize for a metric but don't teach you why. We need the learning from structured experiments first. | Experiment velocity > 60/quarter and team wants to automate low-stakes decisions |
| Real-time ML retraining | Daily batch retraining is sufficient. User engagement patterns don't shift hourly. | Evidence that daily models miss important behavioral shifts |
| Third-party data enrichment | First-party behavioral data is sufficient for current personalization quality. Third-party adds cost and privacy complexity. | First-party feature importance plateaus (diminishing returns from more behavioral signals) |
| Social/community features | We're a personalized individual experience. Social features add complexity and moderation burden. | User research shows strong demand for peer connection |
| Gamification (points, badges, leaderboards) | Extrinsic motivation can undermine intrinsic motivation for health/wellness goals. Streaks are our only gamification, and they're carefully designed. | Research supports gamification for our specific user population |
| White-label / platform offering | Too early. Need to prove the system works for our own product before offering it to others. | System is stable for 6+ months and inbound interest from potential platform customers |
