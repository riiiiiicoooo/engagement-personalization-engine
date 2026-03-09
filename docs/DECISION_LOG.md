# Decision Log: Engagement & Personalization Engine

**Last Updated:** January 2025

---

## How to Read This Document

Each decision follows the same structure: the context that created the decision point, the options considered, the choice we made, the reasoning, and the consequences (both positive and negative). Decisions are numbered chronologically.

---

## DEC-001: Server-Side vs. Client-Side Experiment Assignment

**Date:** February 2024
**Status:** Decided — Server-side
**Stakeholders:** PM, Engineering Lead, Data Science

**Context:**
We needed to build an experiment assignment system. The choice was between evaluating experiments on the client (like Optimizely or LaunchDarkly's client SDKs) or on the server (our own assignment logic in the API layer).

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Client-side (Optimizely/LaunchDarkly) | Fast integration, visual editor, managed infrastructure | Per-seat pricing at scale ($$$), limited targeting flexibility, client SDK adds latency/bundle size, hard to coordinate cross-platform |
| Server-side (custom) | Full control over assignment logic, no per-seat cost, consistent cross-platform, integrates with our segmentation | Build cost (4-6 weeks), no visual editor, we own reliability |

**Decision:** Server-side, custom-built.

**Reasoning:**
Client-side tools work well for simple UI experiments but break down when you need tight integration with user segmentation, engagement scoring, and ML models. Our experiments target specific engagement tiers and lifecycle stages — data that lives server-side. Sending all that context to the client for evaluation adds latency, increases bundle size, and creates a sync problem across iOS, Android, and web.

The cost argument sealed it: LaunchDarkly at our scale (200K+ DAU, 20+ concurrent experiments) would cost $80K+/year. Our server-side system cost 5 weeks of engineering time to build and runs on existing infrastructure.

**Consequences:**
- Positive: Full control over assignment, targeting, and exposure logging. No vendor dependency. Zero incremental cost per experiment.
- Positive: Consistent assignment across platforms — same user always gets same variant regardless of device.
- Negative: No visual editor. PMs can't drag-and-drop UI changes. All experiment variants require engineering implementation behind feature flags.
- Negative: We own uptime. One bad deploy took assignment down for 2 hours in Month 3. Added circuit breaker and fallback (default to control).

---

## DEC-002: Composite Engagement Score vs. Single Metric (DAU/MAU)

**Date:** March 2024
**Status:** Decided — Composite score
**Stakeholders:** PM, Data Science, Product Leadership

**Context:**
We needed a way to measure user engagement that could drive personalization, segmentation, and intervention decisions. The question was whether to use a standard industry metric (DAU/MAU ratio) or build a custom composite score.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| DAU/MAU ratio | Industry standard, easy to benchmark, simple to compute | Too coarse: a user who opens the app and immediately closes it counts the same as a user who completes 3 activities. No individual-level signal. |
| Composite score (recency, frequency, depth, consistency, progression) | Captures engagement quality, not just presence. Individual-level. Drives personalization. | Complex to build and explain. Weights are debatable. No industry benchmark. |

**Decision:** Composite engagement score (0-100), five weighted components.

**Reasoning:**
DAU/MAU tells you how many users showed up. It doesn't tell you whether they got value. We tested both: DAU/MAU correlated with 90-day retention at r = 0.52. Our composite score correlated at r = 0.87. The composite score is a dramatically better predictor of long-term retention because it captures what users do, not just that they appeared.

The composite score also enables personalization in ways DAU/MAU can't. A user with a score of 35 (Tier 4) gets different content than a user with a score of 82 (Tier 1). You can't do that with a binary "active/inactive" metric.

**Weight calibration:** We tested multiple weight configurations and selected the combination that maximized correlation with 14-day churn (AUC 0.84). Recency emerged as the highest-weight component because a sudden stop in activity is the single strongest churn signal — more predictive than frequency or depth alone.

**Consequences:**
- Positive: The score became the backbone of the entire system — segmentation, personalization, intervention triggers, experiment targeting all reference it.
- Positive: Individual-level scores enable proactive intervention before users churn.
- Negative: Harder to benchmark externally (no one else uses our exact formula).
- Negative: Weight calibration requires periodic re-evaluation. We re-calibrate quarterly.

---

## DEC-003: Deterministic Hashing vs. Random Assignment for Experiments

**Date:** February 2024
**Status:** Decided — Deterministic hashing
**Stakeholders:** Engineering Lead, Data Science

**Context:**
Experiment assignment needs to be consistent (same user sees same variant every time) and uniform (50/50 split should be exactly 50/50 at scale). The question was implementation method.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Random assignment (store in DB) | Simple, guaranteed random | Requires DB lookup on every request. Cross-platform inconsistency if DB is delayed. DB failure = no assignment. |
| Deterministic hash (hash(user_id + experiment_id) % 100) | No DB lookup needed, consistent across platforms, works offline | Hash function could have distribution bias. Assignment is predetermined (can't rebalance mid-experiment). |

**Decision:** Deterministic hashing using MurmurHash3.

**Reasoning:**
The critical requirement is that a user sees the same variant on iOS, Android, and web without any of those platforms needing to call the database. `hash(user_id + experiment_id) % 100` produces the same bucket on every platform, every time, with no network call.

We validated MurmurHash3 distribution across 1M synthetic user IDs: the 50/50 split was 500,127 / 499,873 (0.025% deviation). Well within acceptable bounds. We also verified that different experiment_ids produce independent bucket assignments (correlation < 0.001).

**Consequences:**
- Positive: Zero-latency assignment. No DB dependency on critical path.
- Positive: Perfect cross-platform consistency.
- Positive: Reproducible — any engineer can compute a user's assignment locally for debugging.
- Negative: Can't manually rebalance a running experiment (would change everyone's assignment). Instead we adjust rollout percentage.
- Accepted: We cache assignments in Redis anyway for fast lookup, but the hash is the source of truth.

---

## DEC-004: Real-Time vs. Batch Engagement Scoring

**Date:** March 2024
**Status:** Decided — Real-time (event-driven)
**Stakeholders:** PM, Engineering Lead, Data Science

**Context:**
Engagement scores power personalization and intervention triggers. The question was whether to compute scores in real-time (on every event) or in daily batch jobs.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Daily batch (Snowflake → scores table → Redis) | Simple, cheap, easy to debug | 24-hour latency. A user who goes from engaged to disengaged at 9am won't be detected until the next morning. |
| Real-time (event → score update → Redis) | Sub-second latency. Detect disengagement immediately. Enable same-session personalization. | More complex. Higher compute cost. Score can flicker on noisy events. |

**Decision:** Real-time, event-driven scoring with Redis caching.

**Reasoning:**
The intervention system's value depends on speed. A user can go from "healthy" to "at-risk" in a single bad session (app open → frustration → close → uninstall). If we only score daily, we detect this 24 hours later — by which time the user may have already uninstalled. Real-time scoring detects the score drop within the session and can trigger an intervention (in-app message, adjusted content) before the user leaves.

We measured: interventions triggered within 24 hours of score decline had a 38% success rate. Interventions triggered 48+ hours later had a 14% success rate. Speed matters.

**Compute cost:** Real-time scoring adds ~$400/month in Redis and compute costs. Daily batch would cost ~$50/month. The $350 difference is negligible compared to the retention value of timely interventions (estimated $40K/month in prevented churn).

**Flickering mitigation:** We use a 1-hour smoothing window for tier assignments. A single anomalous event can change the raw score, but the user's tier only changes if the score sustains the new level for 1+ hour. This prevents a user from flickering between Tier 2 and Tier 3 on a single bad session.

**Consequences:**
- Positive: Interventions fire 10-20x faster than batch scoring would allow.
- Positive: Same-session personalization adapts (user's content shifts if they complete several activities in one session).
- Negative: More moving parts (event pipeline → scoring service → Redis → API). Added monitoring for pipeline staleness.
- Negative: Score can temporarily reflect incomplete data if events arrive out of order. Smoothing window mitigates this.

---

## DEC-005: Collaborative Filtering vs. Content-Based Recommendations

**Date:** April 2024
**Status:** Decided — Both (hybrid)
**Stakeholders:** PM, Data Science Lead

**Context:**
The recommendation engine needed a ranking model to personalize the content feed. The question was which approach to use.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Content-based only (match content attributes to user preferences) | Simple, interpretable, works for new users with stated preferences | Can't discover unexpected preferences. Creates filter bubbles. "You liked meditation, here's more meditation." |
| Collaborative filtering only (users like you liked X) | Discovers non-obvious preferences. Captures latent patterns. | Cold start problem for new users and new content. Less interpretable. |
| Hybrid (collaborative filtering + content-based + other signals) | Best of both. Collab filter handles discovery, content-based handles cold start. | More complex. Weights need tuning. |

**Decision:** Hybrid model with weighted components.

**Reasoning:**
Content-based alone trapped users in filter bubbles. A user who completed 10 meditation sessions would see nothing but meditation — even though collaborative filtering data showed that users who liked meditation also disproportionately engaged with journaling prompts. Content-based misses these cross-category discoveries.

Collaborative filtering alone had a cold start problem. New users with no interaction history got random recommendations. Content-based filtering, using their onboarding goal selection, provided meaningful recommendations from day one.

The hybrid approach uses collaborative filtering (40% weight) for discovery, content affinity (25%) for reinforcing known preferences, freshness (15%) for surfacing new content, engagement tier adjustment (10%) for difficulty matching, and goal relevance (10%) for maintaining topical alignment.

**Evaluation:** NDCG@10 comparison across approaches:
- Content-based only: 0.58
- Collaborative filtering only: 0.64 (but 0.31 for users with < 10 interactions)
- Hybrid: 0.72 (and 0.55 for users with < 10 interactions)

**Consequences:**
- Positive: 62% lift in content completion rate vs. non-personalized (popularity-based) ranking.
- Positive: Users in the hybrid condition discovered 40% more content categories than content-based-only users.
- Negative: Model complexity increased. Training pipeline takes 45 minutes daily (vs. 5 minutes for content-based).
- Negative: Harder to explain to stakeholders why specific content was recommended. Added "why this recommendation" debug tool for PMs.

---

## DEC-006: Feature Flags Separate From Experiments

**Date:** March 2024
**Status:** Decided — Separate systems
**Stakeholders:** PM, Engineering Lead

**Context:**
Feature flags and experiments both control what users see. Some platforms (LaunchDarkly, Statsig) combine them into one system. The question was whether to keep them separate.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Combined system | Single config surface. Every flag is automatically an experiment. Less tooling. | Different lifecycles create confusion. Flags are permanent infrastructure; experiments are temporary. Team treats permanent flags as "experiments that shipped" — messy. |
| Separate systems | Clear purpose for each. Flags = operational control. Experiments = measurement. Different UI, different lifecycle. | Two systems to maintain. Need to link flags to experiments when a flag gates an experiment variant. |

**Decision:** Separate systems, linked by experiment_id on the flag definition.

**Reasoning:**
In the combined model, we saw a specific failure mode: a PM would ship an experiment, the flag would become "permanent," and 6 months later nobody remembered whether the flag was still being used or if it was safe to remove. The flag count grew to 180+ with no cleanup. Engineers were afraid to touch old flags because they might still be gatekeeping experiments.

Separating them enforces discipline: flags have a lifecycle (created → active → stale alert at 30 days → archived). Experiments have a different lifecycle (draft → active → completed → decision). A flag can gate an experiment variant, but the experiment's completion doesn't automatically affect the flag — a PM must explicitly decide to either roll the flag to 100% (ship) or turn it off (kill).

**Consequences:**
- Positive: Flag hygiene improved dramatically. Stale flag count dropped from 180+ to 23 active flags.
- Positive: Clear separation of concerns. Engineers know flags are permanent and experiments are temporary.
- Negative: Slightly more configuration when setting up an experiment (create flag + create experiment + link them).
- Accepted: The extra configuration step takes ~2 minutes and prevents months of accumulated technical debt.

---

## DEC-007: Sequential Testing for Experiment Analysis

**Date:** April 2024
**Status:** Decided — O'Brien-Fleming spending function
**Stakeholders:** Data Science Lead, PM

**Context:**
PMs wanted to check experiment results before the planned end date. Standard frequentist testing inflates false positive rates with repeated looks ("peeking problem"). We needed a method that allows valid interim analysis.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Fixed-horizon only (no peeking allowed) | Simplest, well-understood, no inflation risk | PMs will peek anyway (they always do). Harmful experiments run longer than necessary. Can't stop early on overwhelming evidence. |
| Sequential testing (alpha spending) | Valid interim looks. Can stop early for clear winners or losers. Controls overall false positive rate. | More complex. Requires spending function choice. Final significance threshold is slightly stricter than 0.05. |
| Bayesian approach only | Natural stopping rules. Probability statements intuitive for PMs. No peeking problem. | Controversial prior selection. Some stakeholders don't trust Bayesian results. Harder to map to traditional power calculations. |

**Decision:** Sequential testing (O'Brien-Fleming spending function) as primary method. Bayesian credible intervals reported alongside as supplementary.

**Reasoning:**
The pragmatic reality: PMs will look at dashboards. Telling them "don't peek" doesn't work. Instead, we built a system where peeking is valid. The O'Brien-Fleming spending function is conservative early (p < 0.0001 to declare a winner at 25% of sample) and progressively relaxes. This means early stops only happen for overwhelming effects — exactly the ones we'd want to stop early anyway.

We report Bayesian credible intervals alongside because PMs find "94% probability that treatment is better" more intuitive than "p = 0.008." But the ship/kill decision is based on the frequentist sequential analysis.

**Consequences:**
- Positive: PMs check results guilt-free. Harmful experiments stopped 3-5 days earlier on average.
- Positive: Two experiments with very large effects (>15% lift) were shipped 10+ days early, accelerating learning velocity.
- Negative: Final-look significance threshold is 0.043 instead of 0.05 (slightly stricter, to compensate for interim looks). Marginally reduces power.
- Negative: PMs sometimes misinterpret interim non-significance as "it's not working" and want to stop early. Training required.

---

## DEC-008: Notification Frequency Capping by Engagement Tier

**Date:** May 2024
**Status:** Decided — Tier-based caps
**Stakeholders:** PM, Growth Lead

**Context:**
Notification opt-out rate was 34%. The growth team wanted to send more notifications to re-engage users. The product team believed we were over-notifying. Classic tension between growth and user experience.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Increase notifications for all users | More touchpoints, more chances to re-engage | Opt-out rate likely increases further. Users who opt out are permanently lost. |
| Decrease notifications for all users | Lower opt-out rate, better user experience | Less re-engagement. Highly engaged users who want notifications get fewer. |
| Tier-based frequency caps | Send more to engaged users (who want it) and less to disengaged users (who are annoyed by it) | More complex. Need to maintain tier-specific rules. |

**Decision:** Tier-based caps (Tier 1: 5/week, Tier 2: 4, Tier 3: 3, Tier 4: 2, Tier 5: 1).

**Reasoning:**
We ran an experiment: three arms (increase all, decrease all, tier-based). Results after 4 weeks:

| Arm | Opt-out Rate | Re-engagement Rate (Tier 4-5) | Net Impact |
|---|---|---|---|
| Increase all | 41% (+7pp) | 18% (+2pp) | Negative — more opt-outs than re-engagements |
| Decrease all | 22% (-12pp) | 11% (-5pp) | Mixed — saved opt-outs but lost re-engagement |
| Tier-based | 18% (-16pp) | 16% (flat) | Best — dramatically fewer opt-outs, maintained re-engagement |

Tier-based capping protected low-engagement users from notification fatigue while maintaining the notification channel for high-engagement users who actually want to hear from us.

**Key insight from the experiment:** Sending fewer notifications to Tier 4-5 users actually maintained their re-engagement rate (16% vs. 16%). The notifications they did receive were higher impact because we sent the best one per week instead of 4 mediocre ones. Quality over quantity.

**Consequences:**
- Positive: Opt-out rate dropped from 34% to 18% within 6 weeks.
- Positive: Notification open rate increased from 16% to 28% (fewer sends, but each one more relevant).
- Negative: Total notification volume dropped ~40%. Required adjusting growth team OKRs to focus on quality (open rate, re-engagement) instead of quantity (sends).

---

## DEC-009: Snowflake for Experiment Analysis vs. In-App Tool

**Date:** February 2024
**Status:** Decided — Snowflake
**Stakeholders:** Data Science Lead, PM, Engineering Lead

**Context:**
We needed to analyze experiment results. The question was whether to build analysis into the product (like Statsig or Eppo) or run analysis in Snowflake.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| In-app analysis tool (built-in or Statsig/Eppo) | Self-serve for PMs. Real-time results. Pretty dashboards. | Limited statistical methods. Can't do custom analyses. Vendor cost ($50K+/year for Eppo at our scale). |
| Snowflake + dbt + notebooks | Full statistical flexibility. Sequential testing, Bayesian, custom metrics. No additional vendor cost (already paying for Snowflake). | Not self-serve for PMs (need data science for complex queries). Slower iteration on dashboards. |

**Decision:** Snowflake for analysis, with a lightweight dashboard for PMs that queries Snowflake.

**Reasoning:**
Statistical rigor was the priority. In-app tools like Statsig provide convenient dashboards but limited statistical methods. We needed sequential testing with alpha spending functions, segment decomposition with multiple comparison correction, novelty detection, and long-term holdout analysis. None of the in-app tools supported all of these.

We built a lightweight experiment dashboard that queries pre-computed results in Snowflake (dbt models run hourly for active experiments). PMs see primary metric, guardrails, and a ship/kill recommendation. For deeper analysis (segment decomposition, novelty checks, custom metrics), data science runs notebooks against Snowflake.

**Consequences:**
- Positive: Full statistical flexibility. We've added sequential testing, Bayesian intervals, novelty detection, and SRM checks — none of which were available in evaluated vendor tools.
- Positive: No additional vendor cost.
- Negative: PM self-serve is limited to the dashboard. Deep analysis requires data science involvement.
- Negative: Dashboard refresh is hourly (not real-time). Acceptable for most experiments; added on-demand refresh for guardrail monitoring.

---

## DEC-010: Feast Feature Store vs. Ad Hoc Feature Engineering

**Date:** April 2024
**Status:** Decided — Feast
**Stakeholders:** Data Science Lead, ML Engineer

**Context:**
ML models (churn prediction, content ranking, clustering) need consistent features at training time and serving time. The data science team was writing features twice — once in Snowflake for training and once in Python for serving — with subtle differences causing training-serving skew.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Continue ad hoc (Snowflake for training, Python for serving) | No new tooling. Fast to iterate. | Training-serving skew caused model accuracy to degrade in production. Features defined in two places. |
| Feast feature store | Single feature definition. Consistent training and serving. Point-in-time correct joins. | New infrastructure to maintain. Learning curve. Adds complexity to the ML pipeline. |
| SageMaker Feature Store | Managed, integrates with SageMaker training | AWS-locked, more expensive, less flexible offline store |

**Decision:** Feast with Snowflake offline store and Redis online store.

**Reasoning:**
Training-serving skew was a real problem, not theoretical. The churn prediction model had AUC of 0.87 in offline evaluation but only 0.79 in production — a gap caused by features computed slightly differently at training vs. serving time. Example: training computed `sessions_14d` using a Snowflake window function with timezone-aware timestamps; serving computed it in Python with UTC timestamps. The feature values differed by 5-10% for users near timezone boundaries.

Feast eliminated this by defining features once and serving them identically for training and inference. After switching to Feast, the training-production AUC gap closed from 0.08 to 0.01.

**Consequences:**
- Positive: Training-serving skew eliminated. Model production accuracy matches offline evaluation.
- Positive: New features are defined once and immediately available for both training and serving.
- Negative: Feature store adds a dependency in the serving path. Redis failure = no features = model falls back to defaults.
- Negative: Learning curve for the team (~2 weeks to become proficient with Feast).

---

## DEC-013: Behavioral Signal-Based Recommendations Over Content-Based Collaborative Filtering

**Date:** October 2024
**Status:** Accepted (supersedes earlier approach)
**Stakeholders:** PM, Data Science Lead, Engineering

**Context:**
First recommendation engine used content-based collaborative filtering — analyzing content attributes (category, duration, difficulty) and finding similar users based on content consumption overlap.

**What Happened:**
Cold start problem was severe. New users (first 7 days) had no content history, so recommendations defaulted to "most popular" — which was the same generic content everyone saw. This segment had 72% churn by Day 14. Even for established users, content-based signals missed intent: a user watching a 5-minute yoga video doesn't necessarily want more yoga — they might be exploring.

**Decision:**
Pivoted to behavioral signals — session patterns (time-of-day, session duration, scroll depth), engagement velocity (how quickly users interact after opening), goal-setting behavior, and completion patterns. Content attributes became secondary features, not primary signals.

**Rationale:**
Behavioral signals are available from first session (no cold start). Early testing showed 3x improvement in Day-7 retention for new users (18% → 54% completion of recommended content). Behavioral clustering identified 6 distinct usage patterns that mapped to real motivation differences.

**Consequences:**
- Required rebuilding the feature pipeline (3 weeks). Lost the "explain why this was recommended" UI feature (behavioral signals are harder to explain than "because you liked similar content"). Added complexity to the ML pipeline. But retention improvement justified the investment.

---

## DEC-011: Intervention Escalation vs. Single Touchpoint

**Date:** June 2024
**Status:** Decided — Graduated escalation
**Stakeholders:** PM, Growth Lead, Content Team

**Context:**
When the engagement scoring system detects an at-risk user, we needed to decide how to intervene. The question was whether to send a single strong notification or a graduated sequence over time.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Single notification (best content, best channel, best time) | Simple. One shot. If it works, great. If not, move on. | 22% success rate in testing. 78% of at-risk users received no further intervention. |
| Graduated escalation (in-app → push → email over 14 days) | Multiple touchpoints increase probability of re-engagement. Each step adapts to user's response. | More complex. Risk of annoying users who don't want to come back. Higher notification volume for at-risk users. |

**Decision:** Graduated escalation with opt-out respect.

**Reasoning:**
We tested both. Single touchpoint: 22% re-engagement within 14 days. Graduated escalation: 44% re-engagement within 14 days. The escalation doubled effectiveness because different users respond to different channels. Some users never check push notifications but open emails. Some never open emails but see in-app messages when they briefly check the app.

The critical design choice: each step only fires if the previous step didn't work. A user who re-engages after the Day 1 in-app message never receives the Day 3 push or Day 7 email. And if a user dismisses the notification at any step, we stop the sequence — we interpret dismissal as "leave me alone," not "try harder."

**Consequences:**
- Positive: 44% intervention success rate (vs. 22% single-touch and 15% no-intervention baseline).
- Positive: Most successful interventions (22%) happen at Day 1 (in-app message), meaning most users who will re-engage do so with the lightest touch.
- Negative: Users who don't respond to all 4 steps have received more notifications than they would have otherwise. Mitigated by frequency caps and opt-out respect.
- Accepted: ~3% of intervention recipients opt out of notifications as a direct result. This is acceptable given the 44% who re-engage.

---

## DEC-012: FastAPI vs. Django for API Layer

**Date:** January 2024
**Status:** Decided — FastAPI
**Stakeholders:** Engineering Lead

**Context:**
The personalization API needs to serve responses within 100ms while making parallel calls to Redis, ML models, and PostgreSQL. Framework choice affects latency profile significantly.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Django REST Framework | Mature ecosystem, team familiarity, built-in admin, ORM | Synchronous by default. Parallel Redis + ML calls require threading/asyncio bolted on. Higher baseline latency (~20ms overhead). |
| FastAPI | Async-native, Pydantic validation, lowest latency profile, excellent for ML serving | Younger ecosystem. No built-in admin. Team less familiar. |
| Flask | Lightweight, flexible, team familiar | No async native. Would need Quart or similar for async. Less structured than either alternative. |

**Decision:** FastAPI.

**Reasoning:**
The personalization pipeline makes 4-5 parallel calls on every request (Redis engagement score, Redis flags, Redis segments, SageMaker ML model, PostgreSQL user profile on cache miss). In Django's synchronous model, these would execute sequentially: 5ms + 5ms + 5ms + 30ms + 10ms = 55ms. In FastAPI with async, they execute in parallel: max(5ms, 5ms, 5ms, 30ms, 10ms) = 30ms. That 25ms savings is the difference between meeting and missing our 100ms budget.

FastAPI's Pydantic models also provide automatic request/response validation and documentation, reducing the API contract bugs that plagued early development.

**Consequences:**
- Positive: p95 latency for /recommend endpoint is 88ms (under 100ms budget).
- Positive: Auto-generated OpenAPI docs from Pydantic models eliminated API contract misunderstandings with mobile team.
- Negative: Team needed 2-3 weeks to ramp up on async Python patterns.
- Negative: No built-in admin UI. Built a lightweight React admin dashboard for experiment and flag management (~3 weeks additional).

---

## DEC-013: Pivot from Frequency-Weighted to Recency-Weighted Engagement Scoring

**Date:** November 2024
**Status:** Decided (supersedes DEC-002 weighting strategy)
**Stakeholders:** PM, Data Science Lead

**Context:**

DEC-002 established the composite engagement score with weighted components. The initial weights were: Recency (15%), Frequency (40%), Depth (20%), Consistency (15%), Progression (10%).

The frequency-heavy model (40% weight) was based on intuition: users who take many actions are more engaged. This made sense from a volume perspective.

**What Happened:**

After 3 months of live A/B testing, the data science team analyzed which score component best predicted 30-day retention (the ultimate goal). Surprising finding:

**Correlation with 30-day retention:**
- Recency (time since last action): r = 0.68
- Frequency (total actions): r = 0.42
- Depth (action types): r = 0.44
- Consistency (days active): r = 0.35
- Progression (level advancement): r = 0.39

**Recency was 60% more predictive than frequency.**

The insight: a user who took 5 actions last week and nothing for 3 weeks is about to churn, regardless of their frequency history. Meanwhile, a user who takes 2 actions per week (low frequency) but consistently does so is sticky.

**Real-world example:**
- User A: Took 200 actions in month 1, then ghosted (recency score degraded immediately)
- User B: Takes 4-5 actions per week consistently for 3 months
- Old model: User A scored higher (frequency 40% weight = high score based on month 1 activity)
- Result: User A churned within 2 weeks; User B remained active and later paid

**Decision:**

Reweighted the engagement score: Recency (30%), Frequency (25%), Depth (20%), Consistency (15%), Progression (10%).

Recency gained 15pp and became the dominant signal. Frequency dropped 15pp.

**Implementation:**
- Recency now decays sharply: no action for 7 days → significant score drop
- Frequency still matters but as a secondary signal
- Same 1-hour smoothing window (prevent single outliers) but weight distribution changed

**Rationale:**

1. **Predictive power:** Recency is 60% more predictive of retention than frequency. Building the score around the strongest signal makes it more actionable.

2. **Practical sense:** In apps, inactivity is the strongest churn signal. A user who hasn't opened the app in 2 weeks is far more likely to churn than a user who opens daily even if the daily user takes fewer actions per session.

3. **Interventions become targeted:** Recency-weighted score immediately flags users with gaps. This allows intervention system to reach out "we notice you haven't checked in, everything okay?" — a natural and well-timed message.

4. **Frequency can mislead:** A user might have high frequency during onboarding (trying features) but then never return. Frequency looks like engagement but isn't.

**Consequences:**

**Short-term:**
- Engagement score distributions shifted (more users now in mid-range tiers)
- Intervention triggers changed (more users now flagged for "hasn't visited in 7+ days")
- Tier assignments changed for ~15% of users

**Long-term:**
- Retention improved: A/B test showed intervention-ready users (flagged by recency drop) had 1.8x higher response rate to "check in" messages vs. previous method of flagging
- Engagement lift improved from +12% to +28% (per original goal)
- Score became much more responsive to actual user behavior

**Comparison of outcomes:**
- Old weighting (frequency 40%): +12% engagement lift, interventions had 0.44 success rate
- New weighting (recency 30%): +28% engagement lift, interventions had 0.78 success rate

The ~2x improvement in intervention success rate indicates that the recency-weighted score was identifying at-risk users far more accurately.

**Lesson:**

Trust the data, not intuition. Frequency as the primary signal felt right intuitively — more actions = more engaged — but the predictive data showed that timing of actions (recency) mattered far more than volume. The shift to recency-weighted scoring was straightforward (just adjust weights) but had outsized impact on product outcomes.
