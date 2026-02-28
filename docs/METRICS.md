# Metrics Framework: Engagement & Personalization Engine

**Last Updated:** January 2025

---

## 1. North Star Metric

**Weekly users who complete a meaningful action aligned with their stated goal.**

Not DAU. Not MAU. Not session count.

A user who opens the app to check a notification and immediately closes it is counted as a daily active user. But they didn't get value. They didn't make progress. They will eventually churn because opening an app isn't satisfying — making progress is.

**Current:** 112,000 weekly goal-aligned active users (56% of WAU)
**Target:** 140,000 (70% of WAU)

**Why this metric:**
- Directly measures whether users are getting value from the product
- Combines engagement (they showed up) with depth (they did something meaningful) and relevance (it connected to their goal)
- Correlates with 90-day retention at r = 0.87 (strongest predictor we've found)
- Moves when we improve personalization, content quality, or intervention effectiveness
- Does NOT move when we inflate vanity metrics (more push notifications → more opens → no more goal-aligned actions)

---

## 2. Growth Model

The growth model connects input levers (things we can change) to the North Star metric through a causal chain.

```
                    ┌─────────────────────────────────────────────┐
                    │           NORTH STAR                         │
                    │  Weekly Goal-Aligned Active Users: 112K     │
                    │  Target: 140K                                │
                    └────────────────────┬────────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────────┐
                    │                    │                         │
              ┌─────▼──────┐    ┌───────▼──────┐    ┌────────────▼──────┐
              │ New Users    │    │ Retained     │    │ Reactivated       │
              │ Activated    │    │ Users        │    │ Users             │
              │              │    │              │    │                   │
              │ 18K/week     │    │ 86K/week     │    │ 8K/week           │
              │ Target: 22K  │    │ Target: 106K │    │ Target: 12K       │
              └──────┬───────┘    └──────┬───────┘    └─────────┬─────────┘
                     │                   │                       │
         ┌───────────┼───────┐    ┌──────┼──────┐         ┌─────┼─────┐
         │           │       │    │      │      │         │     │     │
         ▼           ▼       ▼    ▼      ▼      ▼         ▼     ▼     ▼
      Signup     Onboard  First  Weekly  Depth   Goal   Interv  Win   Return
      Volume     Rate     Key    Return  per    Prog-  ention   back  Depth
                          Action  Rate   Session ress   Rate    Rate
      25K/wk    72%      68%     74%    1.8     62%    38%     12%   1.4
      Tgt:28K   Tgt:78%  Tgt:75% Tgt:80% Tgt:2.2 Tgt:70% Tgt:45% Tgt:18% Tgt:1.8
```

### 2.1 Growth Equation

```
North Star = (New × Activation Rate × Goal Action Rate)
           + (Prior Active × Weekly Return Rate × Goal Action Rate)
           + (Dormant × Reactivation Rate × Return Goal Action Rate)
```

Plugging in current numbers:
```
= (25,000 × 0.72 × 0.68 × 1.0)    New activated users who take goal action
+ (116,000 × 0.74 × 1.0)            Retained users (already goal-aligned by definition)
+ (40,000 × 0.20 × 1.0)             Reactivated dormant users

= 12,240 + 85,840 + 8,000
= ~106,000

(Actual: 112,000 due to some returning users counted in retained)
```

**Biggest lever:** Weekly return rate. Moving it from 74% to 80% adds ~7,000 weekly goal-aligned active users — more than any other single lever. This is why personalization and engagement scoring are the highest-priority investments.

---

## 3. Input Metrics

### 3.1 Acquisition

| Metric | Current | Target | Measurement |
|---|---|---|---|
| Weekly signups | 25,000 | 28,000 | Count of user_signed_up events per week |
| Signup → onboarding completion | 72% | 78% | % who complete onboarding within 24 hours of signup |
| Onboarding → first key action | 68% | 75% | % who complete first meaningful action within 7 days |
| Day-1 retention | 58% | 65% | % who return and take an action within 24 hours of signup |
| Day-7 retention | 45% | 52% | % who take a meaningful action on day 7 |

**Key insight:** The gap between onboarding completion (72%) and first key action (68%) is only 4 percentage points. The real drop is in the following days — getting users to come back after the initial session. Day-1 retention (58%) means 42% of users who complete onboarding never return. The personalized nudge on Day 1 is the most impactful intervention for new users.

### 3.2 Engagement

| Metric | Current | Target | Measurement |
|---|---|---|---|
| Daily active engagement rate | 28.2% | 30% | DAU with meaningful action / total active accounts |
| Weekly return rate | 74% | 80% | % of prior-week active users who return this week |
| Average sessions per week | 3.8 | 4.2 | Mean sessions/week for active users (trailing 14 days) |
| Average session duration | 5.7 min | 6.0 min | Mean session length for sessions with meaningful actions |
| Actions per session | 1.8 | 2.2 | Mean meaningful actions per session |
| Content completion rate | 34% | 38% | % of started content items that are completed |
| Streak maintenance rate | 62% | 68% | % of users with active streak who maintain it week-over-week |

**Key insight:** Content completion rate (34%) tells us that 66% of content users start is abandoned. This isn't a content quality problem — it's a matching problem. Users are starting content that's too long, too hard, or misaligned with their current engagement level. Tier-based content matching (shorter, simpler content for Tier 3-5 users) improved completion from 21% to 34%.

### 3.3 Retention

| Metric | Current | Target | Measurement |
|---|---|---|---|
| 7-day retention | 52% | 58% | % of Day-0 cohort with meaningful action in Day 7 window |
| 30-day retention | 44% | 50% | % with meaningful action in Day 28-30 window |
| 90-day retention | 51% | 55% | % with meaningful action in Day 88-90 window |
| Churn rate (monthly) | 8.2% | 6% | % of active users last month with no activity this month |
| Reactivation rate | 20% | 25% | % of dormant users (14+ days) who return within 30 days |
| Resurrection rate | 12% | 18% | % of churned users (30+ days) who return within 90 days |

**Key insight:** 90-day retention (51%) is actually higher than 30-day retention (44%). This seems paradoxical but makes sense: users who make it past 30 days have built habits, so their retention stabilizes. The critical churn window is days 7-30. This is where personalization has the highest marginal impact — after the novelty of signup fades but before habit formation kicks in.

### 3.4 Personalization Performance

| Metric | Current | Target | Measurement |
|---|---|---|---|
| Recommendation relevance (NDCG@10) | 0.72 | 0.75 | Normalized discounted cumulative gain of top 10 items |
| Churn prediction accuracy (AUC) | 0.84 | 0.85 | Area under ROC curve for 14-day churn model |
| Intervention success rate | 38% | 45% | % of at-risk users who re-engage within 7 days of intervention |
| Notification open rate | 28% | 30% | % of delivered notifications that are opened within 24 hours |
| Notification opt-out rate | 18% | 15% | % of users who disable push notifications (rolling 30 days) |
| Personalization latency (p95) | 88ms | < 100ms | 95th percentile API response time for /recommend endpoint |
| Fallback activation rate | 0.3% | < 1% | % of requests served by fallback (non-personalized) ranking |

### 3.5 Experimentation Velocity

| Metric | Current | Target | Measurement |
|---|---|---|---|
| Experiments per quarter | 52 | 60 | Count of experiments reaching "completed" status |
| Time from hypothesis to live | 4.2 days | 3 days | Median calendar days from experiment creation to first exposure |
| Experiment ship rate | 37% | 35-40% | % of experiments with decision = "ship" |
| Concurrent experiments | 14 | 18 | Active experiments at any point in time |
| SRM incidents | 1/quarter | 0 | Experiments flagged for sample ratio mismatch |

---

## 4. Guardrail Metrics

Guardrails are metrics that must not degrade, even if input metrics are improving. They protect against pathological optimization.

| Guardrail | Current | Floor | Why |
|---|---|---|---|
| Notification opt-out rate | 18% | < 25% | Above 25% means we're destroying the notification channel. Irreversible. |
| App crash rate | 0.3% | < 1% | Above 1% means broken code reaching users. |
| API error rate (5xx) | 0.1% | < 0.5% | Above 0.5% means systemic instability. |
| Personalization latency (p95) | 88ms | < 150ms | Above 150ms means users perceive the app as slow. |
| CSAT (in-app survey, monthly) | 4.2 / 5.0 | ≥ 3.8 | Below 3.8 means user satisfaction is eroding despite metric improvements. |
| Subscription cancellation rate | 4.1% monthly | < 6% | Above 6% means we're losing paying users faster than acquiring them. |
| Data pipeline latency (events → Snowflake) | 3.2 min | < 10 min | Above 10 min means experiment analysis and scoring are dangerously stale. |
| ML model drift (feature distribution) | Within 1 std dev | < 2 std dev | Beyond 2 std dev means the world has changed and models need retraining. |

**Guardrail escalation:**

| Level | Condition | Action |
|---|---|---|
| Watch | Guardrail at 80% of floor | PM notified, added to weekly review |
| Warning | Guardrail at 90% of floor | PM + Engineering notified, daily monitoring |
| Breach | Guardrail exceeds floor | Active experiments paused, investigation required, fix within 48 hours |

---

## 5. Engagement Score Distribution

The engagement score distribution is the most important operational dashboard. It tells us the overall health of the user base at a glance.

### 5.1 Current Distribution

```
Score Distribution (200K active users)

100 ┤
 90 ┤  ██
 80 ┤  ████
 70 ┤  ████████
 60 ┤  ████████████
 50 ┤  ████████████████████
 40 ┤  ██████████████████████████
 30 ┤  ████████████████████████████
 20 ┤  ██████████████████████████████████
 10 ┤  ████████████████████████
  0 ┤  ████████████████
    └──┬──────┬──────┬──────┬──────┬──
       T1     T2     T3     T4     T5
      (16K)  (44K)  (60K)  (48K)  (32K)
       8%     22%    30%    24%    16%
```

### 5.2 Healthy vs. Current

| Tier | Current % | Healthy Target | Direction |
|---|---|---|---|
| Tier 1 (80-100) | 8% | 12% | ↑ Grow through Tier 2 promotion |
| Tier 2 (60-79) | 22% | 28% | ↑ Primary growth target |
| Tier 3 (40-59) | 30% | 30% | ← Stable (natural middle) |
| Tier 4 (20-39) | 24% | 18% | ↓ Reduce through interventions |
| Tier 5 (0-19) | 16% | 12% | ↓ Reduce through reactivation + accepting some churn |

**Key insight:** The biggest opportunity isn't growing Tier 1. It's moving Tier 3 and Tier 4 users up one tier. Moving a user from Tier 3 to Tier 2 increases their 90-day retention from 38% to 67%. Moving them from Tier 4 to Tier 3 increases it from 18% to 38%. Each tier transition roughly doubles retention probability.

---

## 6. Metric Relationships

### 6.1 Leading and Lagging Indicators

```
LEADING (move first)          LAGGING (move later)
─────────────────             ────────────────────
Engagement score         ───► Weekly return rate      ───► 90-day retention
Content completion rate  ───► Session depth           ───► ARPU
Notification open rate   ───► Daily engagement rate   ───► Revenue
Intervention success rate───► Churn rate              ───► LTV
Experiment velocity      ───► Metric improvement rate ───► Business growth
```

**Why this matters:** If you only measure lagging metrics (retention, revenue), you won't know if things are improving or declining until weeks later. Leading metrics give you a 1-2 week early warning. When engagement scores start declining, you know retention will follow — and you have time to intervene.

### 6.2 Key Correlations

Validated through causal analysis (not just correlation — via A/B tests that moved the input and measured the output):

| Input Metric | Output Metric | Relationship |
|---|---|---|
| Engagement score | 90-day retention | +10 points score → +12% retention probability |
| Content completion rate | Weekly return rate | +5pp completion → +3pp return rate |
| Notification open rate | 48-hour re-engagement | +10pp open rate → +7pp re-engagement |
| Sessions per week | Subscription conversion | 3+ sessions/week = 2.8x higher conversion than <3 |
| Streak length | 30-day retention | 7+ day streak = 82% retention vs. 41% without streak |
| Intervention within 3 days of score decline | Reactivation rate | 38% with intervention vs. 15% without |

### 6.3 Metric Traps

Metrics that look good but don't actually mean what you think:

| Trap Metric | Why It's Misleading | What to Measure Instead |
|---|---|---|
| DAU | Counts passive app opens, inflated by notifications | DAU with meaningful action |
| Total push notifications sent | More sends ≠ more engagement; can increase opt-outs | Notification-driven meaningful actions |
| Session count | Can increase by fragmenting sessions (user opens/closes more) | Session duration and depth |
| Onboarding completion rate | Can increase by shortening onboarding, sacrificing activation quality | Day-7 retention of onboarded users |
| Feature adoption rate | New feature may cannibalize existing features, not create new value | Incremental actions (did total actions increase?) |
| Page views | Confusion-driven navigation inflates page views | Task completion rate |

---

## 7. Reporting Cadence

| Report | Audience | Frequency | Key Metrics |
|---|---|---|---|
| North Star dashboard | All product | Real-time | Weekly goal-aligned active users, engagement score distribution |
| Engagement health | PM team | Daily | Tier distribution changes, intervention trigger volume, anomalies |
| Experiment results | PM + data science | Per-experiment completion | Primary metric, guardrails, segment decomposition, decision |
| Retention curves | Product leadership | Weekly | 7/30/90-day retention by cohort, trend vs. 4-week rolling average |
| Personalization performance | ML team + PM | Weekly | Model accuracy, recommendation relevance, fallback rate, latency |
| Business impact | Executive team | Monthly | ARPU, subscription conversion, LTV, retention vs. targets |
| Experiment learning digest | All product + engineering | Monthly | Top learnings, shipped experiments, cumulative impact |
