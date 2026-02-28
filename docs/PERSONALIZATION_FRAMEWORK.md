# Personalization Framework: Engagement & Personalization Engine

**Last Updated:** January 2025

---

## 1. Personalization Philosophy

Personalization isn't showing users what they want to see. It's showing users what they need to see next in order to make progress.

The distinction matters. A user who loves reading articles about stress management doesn't necessarily need another article about stress management. They might need a guided breathing exercise — something they've never tried but that users like them found transformative. "What you want" is preference matching. "What you need next" is personalization that drives outcomes.

Our system personalizes across four dimensions:

| Dimension | What It Means | Example |
|---|---|---|
| **Content** | What the user sees | Recommending a 5-minute meditation vs. a 30-minute workout |
| **Framing** | How it's presented | "Continue your streak" vs. "Start something new" |
| **Timing** | When they see it | Push notification at 7am vs. 9pm based on engagement patterns |
| **Intensity** | How much we ask of them | Power users get advanced challenges; drifting users get low-barrier entry points |

---

## 2. User Segmentation Model

Every user occupies a position across four segmentation dimensions, updated in real time. These dimensions are the foundation of all personalization decisions.

### 2.1 Lifecycle Stage

Where the user is in their journey with the platform.

```
                                    ┌──────────┐
                            ┌──────►│ Engaged  │
                            │       │ (active  │
┌──────────┐  ┌──────────┐ │       │ 2+ weeks)│
│ New       │──►Activated │─┤       └────┬─────┘
│ (day 0-7) │  │(first key│ │            │
└──────────┘  │ action)   │ │       ┌────▼─────┐       ┌──────────┐
               └──────────┘ │       │ At-Risk   │──────►│ Dormant  │
                            │       │(score     │       │(14+ days │
                            │       │ declining)│       │ inactive) │
                            │       └──────────┘       └────┬─────┘
                            │                                │
                            │       ┌──────────┐            │
                            └───────│Reactivated│◄───────────┘
                                    │(returned  │
                                    │after      │
                                    │dormancy)  │
                                    └──────────┘
```

**Transition rules:**

| From | To | Trigger |
|---|---|---|
| New | Activated | First key action completed (not just app open — must be meaningful) |
| Activated | Engaged | Sustained activity for 2+ consecutive weeks (3+ sessions/week) |
| Engaged | At-Risk | Engagement score drops > 15 points in 3 days, OR tier drops by 2+ |
| At-Risk | Dormant | No meaningful action for 14 consecutive days |
| Dormant | Reactivated | Any meaningful action after 14+ day gap |
| Reactivated | Engaged | Sustained activity for 2+ consecutive weeks post-return |
| Any | At-Risk | Churn prediction model outputs > 70% probability within 14 days |

**Why "first key action" and not "first app open":** Opening the app is passive. Completing a meaningful action — finishing content, logging a goal action, completing an activity — demonstrates that the user found value. The gap between "opened" and "acted" is where activation happens. Measuring activation by app opens would overcount and miss the real signal.

### 2.2 Behavioral Cohort

How the user actually behaves on the platform, based on trailing 14-day patterns.

| Cohort | Criteria (Trailing 14 Days) | % of Users | Personalization Implication |
|---|---|---|---|
| **Power** | 7+ sessions/week, 3+ meaningful actions/session | 8% | Advanced content, longer-form, community features, beta access |
| **Regular** | 3-6 sessions/week, 1-2 actions/session | 22% | Maintain momentum, streak mechanics, progressive difficulty |
| **Casual** | 1-2 sessions/week, brief sessions | 30% | Low-barrier content, gentle nudges, simpler CTAs |
| **Drifting** | Was Regular/Power, now declining (session count down > 50% WoW) | 12% | Intervention content, "welcome back" framing, easiest possible re-entry |
| **Dormant** | 0 sessions in 14 days | 20% | Email-only re-engagement, major updates, "here's what you missed" |
| **Churned** | 0 sessions in 30+ days | 8% | Win-back campaigns only, low frequency |

**Why "drifting" is its own cohort:** Most systems only distinguish active from dormant. But the transition from regular engagement to no engagement doesn't happen overnight. There's a drifting phase — maybe 7-14 days — where the user is pulling away but hasn't left yet. This window is where intervention has the highest success rate (3x more effective than trying to reactivate dormant users). Catching users while they're drifting, not after they've disappeared, is the single most impactful capability in the retention system.

### 2.3 Goal Cluster

What the user is trying to accomplish, determined by onboarding survey + behavioral signals.

| Cluster | Onboarding Signal | Behavioral Confirmation | Content Affinity |
|---|---|---|---|
| **A: Weight Management** | Selected weight loss/gain goals | Engages with nutrition content, tracks meals | Meal plans, portion guidance, progress photos |
| **B: Fitness** | Selected exercise/strength goals | Engages with workout content, logs activities | Workout plans, exercise tutorials, challenges |
| **C: Mental Wellness** | Selected stress/anxiety/sleep goals | Engages with meditation, journaling | Guided meditations, breathing exercises, journaling prompts |
| **D: Chronic Condition** | Selected condition management | Engages with condition-specific content, logs vitals | Condition education, symptom tracking, care team messages |
| **E: General Wellness** | Selected general health | Broad engagement, no dominant pattern | Curated mix, "discover" content, seasonal themes |

**Cluster assignment:**
- Initial: k-means clustering on onboarding survey responses
- Refined: behavioral signals update cluster probabilities over first 30 days
- A user can have a primary cluster and a secondary cluster (e.g., primarily Fitness but secondarily Mental Wellness)
- Cluster assignment is re-evaluated monthly but rarely changes after the first 30 days (stable in 91% of users)

### 2.4 Engagement Tier

How engaged the user is right now, based on the composite engagement score.

| Tier | Score Range | Description | Personalization Approach |
|---|---|---|---|
| **Tier 1** | 80-100 | Power users, deeply engaged | Challenge them. Advanced content, beta features, community roles. Don't patronize. |
| **Tier 2** | 60-79 | Regular users, healthy engagement | Maintain momentum. Streaks, progressive difficulty, social proof. |
| **Tier 3** | 40-59 | Casual users, moderate engagement | Lower the bar. Shorter content, simpler asks, celebrate small wins. |
| **Tier 4** | 20-39 | Drifting users, engagement declining | Easiest possible re-entry. 2-minute activities, "just do one thing today." |
| **Tier 5** | 0-19 | Dormant/nearly churned | Reactivation only. Major updates, "we miss you," fresh start options. |

---

## 3. Engagement Scoring

### 3.1 Score Components

The engagement score is a composite of five signals, each capturing a different facet of engagement quality.

```
engagement_score = (
    0.30 × recency_score +        # When did they last do something meaningful?
    0.25 × frequency_score +      # How often do they show up?
    0.20 × depth_score +          # Do they do meaningful things when they show up?
    0.15 × consistency_score +    # Is their engagement pattern regular?
    0.10 × progression_score      # Are they making progress toward their goal?
)
```

**Why these weights:**

Recency gets the highest weight (30%) because it's the strongest leading indicator of churn. A user who was very active last month but hasn't opened the app in 5 days is at higher risk than a user who opens the app every other day at moderate depth. When we tested equal weighting, the score was less predictive of 14-day churn (AUC 0.76 vs. 0.84 with current weights).

Frequency (25%) matters because habitual engagement is the core retention mechanism. Users who engage 3+ times per week have 4.2x higher 90-day retention than users who engage once per week.

Depth (20%) distinguishes meaningful engagement from vanity opens. A user who opens the app and immediately closes it is not truly engaged, even if they do it daily.

Consistency (15%) captures regularity. A user who engages every Tuesday and Thursday is more retained than a user who binge-engages on Saturday and disappears for a week — even though they might have the same weekly frequency.

Progression (10%) ties engagement to the user's stated goal. A user can be active daily but if they're not making progress toward what they signed up for, they will eventually feel that the product isn't working and leave.

### 3.2 Component Calculation

**Recency Score (0-100):**

```
hours_since_last_meaningful_action:
  0-6 hours    → 100
  6-12 hours   → 90
  12-24 hours  → 80
  24-48 hours  → 65
  48-72 hours  → 50
  72-120 hours → 35
  120-168 hours (5-7 days) → 20
  168-336 hours (7-14 days) → 10
  > 336 hours (14+ days) → 0
```

"Meaningful action" = content_completed, goal_action_taken, social_interaction. App opens alone don't count.

**Frequency Score (0-100):**

```
sessions_per_week (trailing 14 days, averaged):
  7+/week → 100
  5-6/week → 85
  3-4/week → 70
  2/week → 50
  1/week → 30
  < 1/week → 10
  0 in 14 days → 0
```

**Depth Score (0-100):**

```
meaningful_actions_per_session (trailing 7 days, averaged):
  3+ actions/session → 100
  2 actions/session → 75
  1 action/session → 50
  app open, browsed only → 25
  app open, immediate close → 10
```

**Consistency Score (0-100):**

```
coefficient_of_variation of daily engagement (trailing 14 days):
  CV < 0.3 (very regular) → 100
  CV 0.3-0.5 → 75
  CV 0.5-0.8 → 50
  CV 0.8-1.2 → 25
  CV > 1.2 (very irregular) → 10
  
Note: Users with < 3 active days have insufficient data.
Default: 50 (neutral) until enough data accumulates.
```

**Progression Score (0-100):**

```
Based on goal completion pace vs. expected pace:
  Ahead of expected → 100
  On track (within 10%) → 80
  Slightly behind (10-25%) → 60
  Behind (25-50%) → 40
  Significantly behind (> 50%) → 20
  No goal set → 50 (neutral)
  No progress in 14 days → 0
```

### 3.3 Score Decay and Updates

The score is updated on every meaningful event and decays over time through the recency component.

**Event-driven updates:** When a user completes an action, the recency component immediately jumps to 100, the depth component is recalculated, and the composite score updates within 500ms (Redis write).

**Time-based decay:** Even without new events, the recency score naturally decays as hours pass. A user with a score of 82 at 9am will have a score of ~75 by the next morning if they don't return — the recency component has degraded from 100 to ~65.

**Score alert thresholds:**

| Alert | Condition | Action |
|---|---|---|
| Rapid decline | Score drops > 15 points in 3 days | Trigger intervention evaluation |
| Tier change | User moves from Tier 2 → Tier 3 or worse | Log segment transition, adjust personalization |
| Approaching dormancy | Score drops below 20 | Queue for dormancy prevention campaign |
| Reactivation | Score rises from < 10 to > 30 | Switch to "welcome back" content strategy |

---

## 4. Recommendation Engine

### 4.1 Two-Stage Architecture

```
Stage 1: CANDIDATE GENERATION          Stage 2: RANKING
(Filter the catalog to ~100             (Score and order the ~100
relevant items)                         candidates for the user)

Content catalog                         Collaborative filtering score
(thousands of items)                    Content affinity score
        │                               Freshness boost
        ▼                               Engagement tier adjustment
Filter by:                              Goal relevance score
├── Goal cluster match                          │
├── Lifecycle stage fit                         ▼
├── Content type variety                Post-ranking adjustments
├── Not seen in 48 hours                ├── Diversity enforcement
├── Not previously completed            ├── Position bias correction
├── Platform compatibility              └── Experiment overrides
        │                                       │
        ▼                                       ▼
~100 candidates                         Top 20 ranked items
                                        returned to client
```

**Why two stages:** Running the full ranking model on every item in the catalog is expensive (~30ms for 100 candidates but ~300ms for 2,000). Candidate generation uses cheap filters to reduce the set, then the expensive ML model ranks the smaller set.

### 4.2 Ranking Model

The ranking model scores each candidate item for a specific user. The score predicts the probability that the user will meaningfully engage with this content (not just view it, but complete it or take an action from it).

```
ranking_score = (
    0.40 × collaborative_filtering_score +
    0.25 × content_affinity_score +
    0.15 × freshness_boost +
    0.10 × engagement_tier_adjustment +
    0.10 × goal_relevance_score
)
```

**Collaborative Filtering (40%):**

Uses Alternating Least Squares (ALS) on the user-item interaction matrix. The matrix tracks which users engaged with which content items. ALS finds latent factors that explain these interactions and predicts which unseen items a user is likely to engage with.

```
User-Item Interaction Matrix:

              Article_1  Activity_2  Meditation_3  Workout_4  ...
User_A           5          3            0            4       
User_B           0          4            5            0       
User_C           4          0            3            5       
User_D (new)     3          ?            ?            ?       

ALS predicts: User_D would likely rate Activity_2 = 3.5, Meditation_3 = 2.1, Workout_4 = 4.2
→ Recommend Workout_4 highest
```

Trained daily on trailing 90 days of interaction data. NDCG@10 = 0.72. Re-evaluated weekly; alert if NDCG drops below 0.65.

**Content Affinity (25%):**

Based on the user's individual interaction history. Categories and content types they've engaged with most frequently get higher affinity scores. This is simpler than collaborative filtering but captures strong individual preferences.

```
User has completed 15 meditation sessions, 3 workout sessions, 1 nutrition article.
Meditation content affinity: 15/19 = 0.79
Workout content affinity: 3/19 = 0.16
Nutrition content affinity: 1/19 = 0.05
```

**Freshness Boost (15%):**

New content gets a temporary ranking lift to ensure it's seen by enough users to generate interaction data for collaborative filtering. Without freshness boost, new content would never rank well because it has no interaction history — a cold start problem.

```
days_since_published:
  0-3 days  → 1.0 boost
  3-7 days  → 0.7 boost
  7-14 days → 0.3 boost
  14+ days  → 0.0 boost
```

**Engagement Tier Adjustment (10%):**

Content difficulty is matched to user engagement level. Tier 4-5 users (drifting/dormant) get simpler, shorter, lower-barrier content. Tier 1-2 users get advanced, longer-form, challenging content.

| Tier | Content Adjustment |
|---|---|
| Tier 1-2 | Boost long-form (15+ min), advanced content, challenges |
| Tier 3 | Neutral — no adjustment |
| Tier 4-5 | Boost short-form (< 5 min), beginner content, "quick win" activities |

Rationale: A drifting user does not need a 30-minute deep-dive workout. They need a 3-minute stretching routine that feels achievable. Meeting users where they are — not where we wish they were — is how we prevent churn.

**Goal Relevance (10%):**

Content tagged with the user's goal cluster gets a boost. Content from the user's secondary cluster gets a smaller boost. Content from unrelated clusters gets no boost (but isn't penalized — serendipitous discovery is valuable).

### 4.3 Diversity Enforcement

Without diversity enforcement, the ranking model tends to recommend clusters of similar items (5 meditation articles in a row). This is boring and limits discovery.

**Rules:**
- Maximum 2 items from the same content category in the top 10
- Maximum 3 items from the same content type (article, activity, meditation, workout) in the top 10
- At least 1 item from a category the user hasn't tried in the last 7 days ("discovery slot")
- At least 1 item from the user's secondary goal cluster in the top 10

**Implementation:** Post-ranking reordering. After scoring, walk through the ranked list and swap items that violate diversity rules with the next-highest-scoring item that doesn't.

### 4.4 Position Bias Correction

Users are more likely to engage with items near the top of the feed simply because they see them first, not because they're better. This creates a feedback loop: top-ranked items get more engagement → model learns they're "better" → ranks them higher → more engagement.

**Correction:** Train the model with position as a feature, then set position to a constant at inference time. This removes the model's reliance on position and forces it to rank based on content quality and user relevance.

### 4.5 Cold Start

New users have no interaction history. New content has no engagement data.

**New user cold start:**
1. Days 0-3: Rank by onboarding survey goal → goal cluster content, sorted by overall popularity
2. Days 3-7: Begin incorporating early interaction signals (content affinity builds)
3. Days 7-14: Collaborative filtering starts contributing (enough data to find similar users)
4. Days 14+: Full personalization active

**New content cold start:**
1. Freshness boost ensures visibility for first 7-14 days
2. Content tagged with metadata (category, difficulty, duration, goal relevance) enables rule-based filtering
3. After 50+ user interactions, collaborative filtering can rank it effectively
4. Content with < 10 interactions after 14 days is flagged for review (may need better positioning or may be low quality)

---

## 5. Notification Personalization

### 5.1 What to Send

Notification content is selected based on the user's lifecycle stage and engagement trend.

| Lifecycle Stage | Engagement Trend | Notification Strategy |
|---|---|---|
| New (day 0-7) | — | Onboarding guidance: "Here's your first [goal] activity" |
| Activated | Improving | Momentum: "You're on a 5-day streak! Keep it going." |
| Activated | Stable | Encouragement: "Ready for today's activity? It's a quick one." |
| Engaged | Stable | Maintenance: "New [goal-relevant] content just dropped." |
| Engaged | Declining | Gentle check-in: "We noticed you've been busy. Here's a 3-min reset." |
| At-Risk | Declining | Low-barrier re-entry: "Just one activity today. 2 minutes. You've got this." |
| Dormant | — | Win-back: "We've added 12 new [goal] activities since your last visit." |
| Reactivated | Improving | Celebration: "Welcome back! You completed 3 activities this week." |

### 5.2 When to Send

Per-user send time optimization, learned from historical notification open patterns.

**Model:** Logistic regression predicting whether a user will open a notification within 2 hours, given the hour of day (in user's local timezone), day of week, and platform.

**Accuracy:** 68% (predicts the correct 2-hour window). Good enough to be meaningfully better than a fixed time.

**Fallbacks:**
- New users with no open history: 10am local time (highest overall open rate across all users)
- Users who haven't opened any of last 5 notifications: suppress (reduce frequency, don't optimize timing for someone who's ignoring you)

**Quiet hours:** Enforced globally (11pm-7am local time) unless user has explicitly opted into late/early notifications. No exceptions.

### 5.3 How Much to Send

Notification frequency is capped by engagement tier. The principle: the less engaged a user is, the fewer notifications they should receive. Over-notifying drifting users accelerates their departure.

| Tier | Max/Week | Channels | Rationale |
|---|---|---|---|
| Tier 1 (Power) | 5 | Push, email, in-app | High engagement = high tolerance. But still cap — even power users have limits. |
| Tier 2 (Regular) | 4 | Push, email, in-app | Maintain momentum without crowding. |
| Tier 3 (Casual) | 3 | Push, email | Lighter touch. In-app only if they open organically. |
| Tier 4 (Drifting) | 2 | Push (gentle), email | Minimal. Each notification is high-stakes — must be relevant. |
| Tier 5 (Dormant) | 1 | Email only | One thoughtful email per week max. Push from a dormant app is annoying. |

**Fatigue detection:**
- If a user dismisses 3 consecutive push notifications → downgrade to email only for 2 weeks
- If a user doesn't open any of 5 consecutive emails → reduce to 1/month
- If a user opts out of a channel → respect immediately, never re-enable without explicit opt-in

**Result:** Notification opt-out rate dropped from 34% to 18% after implementing tier-based frequency capping. Counter-intuitive: sending fewer notifications to low-engagement users actually improved their re-engagement rates because the notifications they did receive were more relevant and less annoying.

---

## 6. Intervention System

### 6.1 When to Intervene

Interventions are proactive outreach to users detected as at-risk by the engagement scoring system and the churn prediction model.

**Intervention triggers:**

| Trigger | Condition | Confidence |
|---|---|---|
| Score rapid decline | Engagement score drops > 15 points in 3 days | High (direct observation) |
| Tier demotion | User moves from Tier 2 → Tier 3 or Tier 3 → Tier 4 | High (confirmed behavioral change) |
| Churn prediction | ML model predicts > 70% churn probability within 14 days | Medium (model accuracy AUC 0.84) |
| Inactivity | No meaningful action in 7 days (for previously active user) | High (direct observation) |

### 6.2 Intervention Escalation

Interventions follow a graduated sequence. Each step is more direct than the last, but only fires if the previous step didn't re-engage the user.

```
Day 0: Trigger detected
       │
       ▼
Day 1: In-app message (next time user opens app)
       "We have a new 3-minute [goal-relevant] activity just for you."
       │
       ├── User re-engages? → Intervention success. Stop sequence.
       │
       ▼
Day 3: Push notification (if push enabled)
       "Your [streak/progress] is at risk. Quick 2-min activity to get back on track."
       │
       ├── User re-engages? → Intervention success. Stop sequence.
       │
       ▼
Day 7: Email with personalized content digest
       "Here's what's new since [last visit]. 3 activities matched to your goals."
       │
       ├── User re-engages? → Intervention success. Stop sequence.
       │
       ▼
Day 14: Final email — major value proposition
       "We've made some big updates. Here's a fresh start plan for [goal]."
       │
       ├── User re-engages? → Intervention success, user enters "Reactivated" stage.
       │
       └── No response → User classified as Dormant. Enter low-frequency win-back cadence.
```

### 6.3 Intervention Effectiveness

| Metric | Value |
|---|---|
| Interventions triggered per month | ~3,200 |
| Re-engagement within 7 days of intervention start | 38% |
| Re-engagement within 14 days | 44% |
| Re-engagement without intervention (control baseline) | 15% |
| Incremental re-engagement attributable to interventions | +29 percentage points |
| Median time to re-engagement (when successful) | 3.2 days |
| Most effective step | In-app message (Day 1): 22% re-engagement |
| Least effective step | Final email (Day 14): 6% re-engagement |

**Key insight:** The in-app message (Day 1) is by far the most effective intervention. This makes sense — if the user still opens the app, even briefly, they're much more recoverable than a user who requires a push or email to come back. This is why we invest heavily in detecting at-risk users early (while they're still opening the app occasionally) rather than waiting until they've gone silent.

---

## 7. Personalization Performance

### 7.1 Model Accuracy

| Model | Metric | Current | Target | Evaluation Frequency |
|---|---|---|---|---|
| Churn prediction (XGBoost) | AUC-ROC | 0.84 | > 0.80 | Daily (compared to 14-day outcome) |
| Content ranking (ALS collaborative filtering) | NDCG@10 | 0.72 | > 0.65 | Weekly |
| User clustering (k-means) | Silhouette score | 0.61 | > 0.55 | Monthly |
| Send time optimization (logistic regression) | Accuracy (2-hour window) | 0.68 | > 0.60 | Weekly |

### 7.2 Personalization Lift

Measured via A/B tests comparing personalized experience vs. non-personalized (popularity-based ranking, generic notifications, no intervention system).

| Component | Metric | Personalized | Non-Personalized | Lift |
|---|---|---|---|---|
| Content recommendations | Content completion rate | 34% | 21% | +62% |
| Notification optimization | Notification open rate | 28% | 16% | +75% |
| Engagement scoring + interventions | 14-day reactivation rate | 44% | 15% | +193% |
| Overall platform | 90-day retention | 51% | 32% | +59% |

### 7.3 Graceful Degradation

When personalization components fail, the system falls back to progressively simpler strategies.

| Failure | Fallback | User Impact |
|---|---|---|
| ML model unavailable | Rule-based ranking: goal cluster × popularity × recency | Slightly less relevant feed. Most users wouldn't notice. |
| Feature store unavailable | Use cached engagement score (Redis). If Redis down, use default Tier 3 content. | Generic content for duration of outage. |
| Segment data stale | Use last known segment membership. If > 24h stale, treat as Tier 3. | Possible mismatch (e.g., user recently became at-risk but still getting Tier 2 content). |
| Notification model unavailable | Send at 10am local time (global default). | Slightly lower open rate but no user harm. |
| All personalization services down | Static content feed sorted by recency. | Users see "what's new" instead of "what's relevant." Functional but generic. |

The principle: personalization failing should never mean the product fails. Every component has a fallback that delivers a usable (if less optimized) experience. No blank screens, no error messages, no loading spinners.
