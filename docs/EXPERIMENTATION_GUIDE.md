# Experimentation Guide: Engagement & Personalization Engine

**Last Updated:** January 2025

---

## 1. Why This Guide Exists

Before this platform, the team ran 3-5 experiments per quarter by asking engineering to hard-code A/B splits. Results were analyzed in spreadsheets. Statistical rigor was absent. Most product decisions were based on intuition or the loudest voice in the room.

Now we run 50+ experiments per quarter. Any PM can create, launch, and analyze an experiment without an engineering deploy. This guide documents how to do it right — from hypothesis to decision — so every experiment produces a trustworthy result that compounds our learning.

This is not a statistics textbook. It's a practical playbook for product teams.

---

## 2. Experiment Design

### 2.1 The Hypothesis Template

Every experiment starts with a hypothesis. No hypothesis, no experiment.

**Template:**

```
We believe that [change]
for [user segment]
will cause [expected behavior change]
which we will measure by [primary metric]
and we expect a [X%] improvement within [timeframe].

We will know we are wrong if [guardrail metric] degrades by more than [threshold].
```

**Good example:**

```
We believe that adding progress indicators to the home feed
for activated users (completed onboarding, lifecycle_stage = 'activated')
will cause increased daily return visits
which we will measure by 7-day retention rate
and we expect a 5% relative improvement within 3 weeks.

We will know we are wrong if average session duration decreases by more than 10%.
```

**Bad example:**

```
Let's try a new home feed design and see if people like it.
```

The bad example has no specific change, no target segment, no measurable outcome, no expected effect size, and no guardrail. It will produce a result that nobody trusts and nobody acts on.

### 2.2 Choosing the Primary Metric

The primary metric is the one number that determines whether the experiment ships. Choose carefully.

**Rules:**

1. **One primary metric.** Not two. Not "retention and engagement." If you need to improve two things, run two experiments. Multiple primary metrics inflate your false positive rate (the more metrics you test, the more likely one will be "significant" by chance).

2. **Sensitive enough to detect your expected effect.** If you expect a 2% lift in annual revenue, you'll need millions of users and months of runtime. Find a closer proxy — weekly engagement rate, conversion rate, session count — that moves faster and is causally connected to the downstream metric.

3. **Causally connected to the change.** If you're changing the home feed, measure engagement with the home feed, not unrelated metrics like account settings visits.

4. **Not easily gamed.** If your metric is "clicks on the new button," you can increase clicks by making the button bigger and more annoying. Use downstream metrics: did the click lead to a completed action?

**Metric selection framework:**

| Change Type | Good Primary Metrics | Avoid |
|---|---|---|
| Content/feed changes | Content completion rate, session depth, 7-day retention | Page views (inflated by confusion), time on page (could be frustration) |
| Notification changes | Notification open rate, 48-hour re-engagement rate | Send volume (you control this), unsubscribe rate alone (lagging) |
| Onboarding changes | First key action rate, day-7 retention, activation rate | Completion rate of onboarding itself (could be shorter but worse) |
| UI/UX changes | Task completion rate, error rate, session duration | Click rate on changed element (doesn't measure outcome) |
| Pricing/monetization | Conversion rate, revenue per user, trial-to-paid rate | Sign-up rate alone (doesn't capture downstream value) |

### 2.3 Guardrail Metrics

Guardrails are metrics that must not get worse. They protect against optimizing the primary metric at the expense of something important.

**Standard guardrails (applied to every experiment by default):**

| Guardrail | Threshold | Rationale |
|---|---|---|
| Crash rate | Must not increase by > 0.5% absolute | Broken code |
| App load time (p95) | Must not increase by > 200ms | Performance regression |
| Notification opt-out rate | Must not increase by > 1% absolute | User trust erosion |
| Error rate (API 5xx) | Must not increase by > 0.1% absolute | System stability |

**Context-specific guardrails (PM adds based on experiment type):**

| Experiment Area | Common Guardrails |
|---|---|
| Feed/content changes | Session duration, content completion rate |
| Notification changes | Opt-out rate, app uninstall rate |
| Onboarding changes | Onboarding completion rate, day-1 retention |
| Monetization changes | Daily active users, engagement score |

**Auto-stop rule:** If any guardrail metric is significantly worse in treatment vs. control (p < 0.01, one-sided), the experiment is automatically paused and the PM is alerted. This threshold is stricter than the primary metric test (p < 0.05) because guardrail violations indicate harm.

### 2.4 Sample Size and Runtime

**How many users do you need?**

The required sample size depends on three things:
1. **Baseline rate** of your primary metric (e.g., current 7-day retention is 45%)
2. **Minimum detectable effect (MDE)** — the smallest improvement worth detecting
3. **Statistical power** (80% standard) and **significance level** (α = 0.05 standard)

**Quick reference (two-sided test, 80% power, α = 0.05):**

| Baseline Rate | 2% Relative Lift | 5% Relative Lift | 10% Relative Lift |
|---|---|---|---|
| 10% | 358,000/arm | 57,500/arm | 14,500/arm |
| 25% | 115,000/arm | 18,500/arm | 4,700/arm |
| 50% | 63,000/arm | 10,200/arm | 2,600/arm |
| 75% | 26,000/arm | 4,200/arm | 1,100/arm |

**Estimated runtime = (users per arm × 2) / daily eligible users**

Example: You need 10,200 users per arm. You have 8,000 eligible users per day. Runtime = 20,400 / 8,000 ≈ 3 days (with full traffic), or ~6 days at 50% rollout.

**Rules of thumb:**
- If runtime > 30 days → find a more sensitive proxy metric or accept larger MDE
- If runtime < 3 days → run for at least 7 days anyway (to capture day-of-week effects)
- Always run for at least one full week to account for weekday/weekend behavioral differences

### 2.5 Targeting

Experiments can target specific user segments. This is useful when:
- The change only applies to certain users (e.g., new onboarding flow → target new users only)
- You want to test a hypothesis about a specific cohort (e.g., "this will help at-risk users")
- You want to reduce noise by focusing on users most likely to be affected

**Available targeting dimensions:**

| Dimension | Values | Example |
|---|---|---|
| Lifecycle stage | new, activated, engaged, at_risk, dormant, reactivated | Target "at_risk" for intervention experiments |
| Engagement tier | 1, 2, 3, 4, 5 | Target tier 2-3 for engagement optimization |
| Goal cluster | A (weight), B (fitness), C (mental), D (chronic), E (wellness) | Target cluster-specific content changes |
| Platform | ios, android, web | Platform-specific UI experiments |
| Subscription | free, trial, active, cancelled | Monetization experiments on free users |
| Days since signup | Range | Target users in their first 30 days |
| Custom segments | PM-defined rules | Any combination of the above |

---

## 3. Experiment Execution

### 3.1 Assignment

**Method:** Deterministic hashing.

```
bucket = hash(user_id + experiment_id) % 100
```

Every user gets a consistent bucket number (0-99) for each experiment. The variant mapping determines which buckets map to which variants.

**Example:**

| Variant | Bucket Range | Traffic |
|---|---|---|
| Control | 0-49 | 50% |
| Treatment A | 50-99 | 50% |

**Why deterministic hashing:**
- Same user always sees the same variant (no flickering between sessions)
- Consistent across platforms (iOS, Android, web all compute the same bucket)
- No database lookup required on every page load
- Statistically equivalent to random assignment (hash function distributes uniformly)

**Why not random assignment:**
A user who sees the new feed on Monday and the old feed on Tuesday can't give us a clean signal. The experiment becomes noisy and the user experience is confusing. Deterministic hashing eliminates this.

### 3.2 Exposure Logging

Assignment ≠ exposure. A user is **assigned** when they're bucketed into a variant. A user is **exposed** when they actually see the variant.

**Why this matters:** If you assign 10,000 users to the treatment but only 6,000 open the app during the experiment, your intent-to-treat analysis (all 10,000) will dilute the true effect. Analyzing only exposed users (6,000) gives you a cleaner signal — but introduces selection bias if exposure correlates with behavior.

**Our approach:**
- Log exposure on every feature flag evaluation that gates the experiment
- Primary analysis: intent-to-treat (all assigned users) — conservative but unbiased
- Secondary analysis: exposed-only — larger effect size but interpret with caution
- Report both

### 3.3 Progressive Rollout

New experiments don't launch to 50% immediately. We ramp up to catch issues early.

```
Day 1:    5% of eligible users
          │
          ├── Check: any crashes? errors? guardrail red?
          │
Day 2:    20%
          │
          ├── Check: SRM? guardrail monitoring healthy?
          │
Day 3-4:  50% (full experiment traffic)
          │
          ├── Run for planned duration
          │
Analysis: After planned runtime + 7-day holdout check
```

**Ramp halt conditions (any one triggers pause):**
- Crash rate increase > 0.5%
- API error rate increase > 0.1%
- SRM detected (assignment ratio > 1% off expected)
- Any guardrail significantly worse

### 3.4 Mutual Exclusion

Some experiments can't run simultaneously because they touch the same surface. If Experiment A changes the home feed layout and Experiment B changes home feed content ranking, a user in both sees a combined effect that neither experiment can measure cleanly.

**Mutual exclusion groups:**

| Group | Description | Rule |
|---|---|---|
| home_feed | Experiments affecting home feed layout, content, or ranking | Max 1 active experiment per user |
| notifications | Experiments affecting notification content, timing, or frequency | Max 1 active experiment per user |
| onboarding | Experiments affecting the onboarding flow | Max 1 active experiment per user |
| pricing | Experiments affecting pricing, paywall, or subscription flow | Max 1 active experiment per user |

Users are assigned to only one experiment per mutual exclusion group. If a user is already assigned to an active experiment in a group, they are ineligible for any new experiment in that group.

**Experiments in different groups can run simultaneously.** A user can be in a home feed experiment AND a notification experiment at the same time, because these are independent surfaces.

---

## 4. Analysis

### 4.1 When to Analyze

**Wrong:** Check results every day and make a decision when it "looks significant."

**Right:** Wait for the planned runtime to complete, then analyze once.

**Why:** Checking daily ("peeking") inflates your false positive rate. At α = 0.05, if you check results every day for 14 days, your actual false positive rate can be as high as 25%. You'll think the experiment worked when it didn't.

**Exception:** We use sequential testing (see Section 4.3) which allows valid peeking with controlled error rates. But even with sequential testing, don't make ship decisions early unless the effect is very large and you've run for at least one full week.

### 4.2 Primary Analysis

**Frequentist test (default):**

For proportion metrics (conversion rate, retention rate):
- Two-sample z-test for proportions
- Two-sided (we want to detect both positive AND negative effects)
- α = 0.05, power = 0.80
- Report: point estimate (lift %), 95% confidence interval, p-value

For continuous metrics (session duration, revenue):
- Welch's t-test (doesn't assume equal variances)
- Same α and power
- Report: difference in means, 95% confidence interval, p-value

**Bayesian supplement (reported alongside):**
- Probability that treatment is better than control
- Expected lift (posterior mean)
- 95% credible interval
- Useful for communicating results to non-statisticians: "There is a 94% probability that this change improves retention by 3-7%"

**Decision framework:**

| Result | p-value | Bayesian P(treatment > control) | Decision |
|---|---|---|---|
| Clear win | < 0.05 | > 95% | Ship (if guardrails clean) |
| Promising | 0.05 - 0.10 | 85-95% | Extend runtime or iterate and re-test |
| Inconclusive | 0.10 - 0.50 | 50-85% | Likely underpowered. Increase sample or find better metric. |
| No effect | > 0.50 | 40-60% | Kill. Document learning. |
| Negative | < 0.05, wrong direction | < 5% | Kill immediately. Investigate why. |

### 4.3 Sequential Testing

We use sequential testing to allow valid "peeking" at results before the planned end date. This is important because sometimes an experiment is clearly harmful and should be stopped early, and sometimes the effect is so large that we don't need the full sample.

**Method:** Alpha spending function (O'Brien-Fleming boundaries).

The spending function controls how much of your α budget is "spent" at each interim look. Early looks use very strict thresholds (requiring overwhelming evidence), later looks use progressively weaker thresholds.

| Look | % of Sample | Required p-value to declare winner |
|---|---|---|
| 1 (25% of planned sample) | 25% | < 0.0001 |
| 2 (50%) | 50% | < 0.004 |
| 3 (75%) | 75% | < 0.019 |
| 4 (100% — planned end) | 100% | < 0.043 |

**Practical impact:** You can check results at any point and trust the decision — as long as you use the sequential p-value threshold, not the standard 0.05.

### 4.4 Segment Decomposition

After the primary analysis, decompose results by key segments to understand who is most (and least) affected.

**Standard decomposition dimensions:**

| Dimension | Why |
|---|---|
| Platform (iOS / Android / Web) | Technical differences may cause different effects |
| Engagement tier (1-5) | Highly engaged users may respond differently than dormant |
| Lifecycle stage | New users vs. established users may have different responses |
| Goal cluster | Content changes may only matter for certain goal types |
| Subscription status | Free vs. paid users have different value |

**Important:** Segment decomposition is exploratory, not confirmatory. If the overall experiment is not significant but one segment shows significance, this is NOT evidence that the treatment works for that segment. It's a hypothesis for a future experiment targeting that segment specifically.

### 4.5 Novelty and Primacy Effects

**Novelty effect:** Users engage more with something simply because it's new, not because it's better. The lift you see in week 1 may disappear by week 3.

**Primacy effect:** Users stick with familiar patterns and resist change. The negative effect you see in week 1 may disappear as users adapt.

**Detection method:** Compare the treatment effect in week 1 vs. week 3. If the effect in week 3 is < 50% of the week 1 effect, novelty is likely inflating your result. If the negative effect in week 3 is < 50% of week 1, primacy bias may be masking a real improvement.

**Practical rule:** For any UI or experience change, run the experiment for at least 3 weeks before making a ship decision. For under-the-hood changes (algorithm, ranking, timing), 2 weeks is usually sufficient because users don't consciously notice the change.

### 4.6 Long-Term Holdouts

For experiments that ship, we maintain a 5% holdout group that never receives the change. This group is measured at 30, 60, and 90 days to check for persistent effects.

**Why:** Some changes produce short-term lifts that fade. Others produce delayed benefits that only appear after weeks. The holdout catches both.

**Holdout rules:**
- 5% of the eligible population, assigned at experiment start
- Holdout assignment is permanent for the duration of the holdout period
- Holdout analysis at 30, 60, and 90 days post-ship
- If the effect is no longer significant at 90 days, investigate whether the change is still worth maintaining

---

## 5. Common Pitfalls

### 5.1 Sample Ratio Mismatch (SRM)

If you assign 50/50 but observe 52/48, something is broken. This is a sample ratio mismatch.

**Common causes:**
- Bug in the assignment code (hash function not distributing evenly)
- Bot traffic not filtered out (bots may be concentrated in one variant)
- Users in one variant triggering more events (inflating their count)
- Redirect experiments where the redirect fails for some users

**Detection:** Chi-squared test on assignment counts. Alert threshold: p < 0.001.

**Action:** Pause the experiment. Do NOT analyze results — they are unreliable. Fix the root cause and re-run.

### 5.2 Interference

Users in the treatment group may affect users in the control group.

**Example:** You test a social sharing feature. Treatment users share content with control users. Control users benefit from the feature without being in the treatment group. The measured effect is smaller than the true effect.

**Mitigation:**
- For social features: randomize at the network cluster level, not individual user level
- For marketplace features (if applicable): randomize at the market level
- For most engagement features: individual randomization is fine (no interference)

### 5.3 Multiple Testing

Running 20 experiments simultaneously means that, by chance alone, 1 of them will show a "significant" result at α = 0.05.

**Our approach:**
- Each experiment has exactly ONE primary metric (not multiple)
- We do NOT apply Bonferroni correction across experiments (each experiment is an independent decision)
- We DO apply correction within segment decomposition (when looking at 5 segments within one experiment, adjust for 5 comparisons)
- Bayesian analysis provides natural protection against multiple testing through the prior

### 5.4 Survivorship Bias

If your experiment affects whether users stay in the measurement window, your analysis is biased.

**Example:** You test a notification that brings back dormant users. Treatment group has more active users (because the notification worked). You measure session duration for active users. Treatment looks better — but only because you reactivated low-engagement users who brought down the average in treatment.

**Mitigation:** Always analyze based on the original assignment pool, not conditional on being active during the experiment period (intent-to-treat analysis).

---

## 6. Experiment Repository

Every experiment — shipped, killed, or inconclusive — is documented in a searchable repository. This is how we compound learning over time.

### 6.1 Entry Template

```
Experiment: EXP-041 Progress Indicators on Home Feed
Status: Shipped
Dates: Jan 5 - Jan 23, 2025

Hypothesis:
Adding progress indicators showing goal completion percentage
to the home feed for activated users will increase 7-day retention
by 5% relative.

Target: lifecycle_stage = 'activated'
Primary metric: 7-day retention rate
Guardrails: session duration (must not decrease > 10%), crash rate

Results:
- Sample: 24,100 users (12,050 per arm)
- 7-day retention: +6.2% relative (control: 44.8%, treatment: 47.6%)
- p-value: 0.008
- 95% CI: [+1.8%, +10.6%]
- P(treatment > control): 97.2%
- Guardrails: all clean

Segment decomposition:
- Strongest effect: Tier 3 (casual) users (+9.1%)
- Weakest effect: Tier 1 (power) users (+1.8%, not significant)
- No platform difference (iOS ≈ Android ≈ Web)

Novelty check: Week 1 effect +7.8%, week 3 effect +5.4%. Some novelty decay
but persistent meaningful effect.

Decision: Ship to 100%
Rationale: Clear positive result on primary metric. Strongest for the users
who need it most (Tier 3 casual users). Minimal novelty decay.
Long-term holdout in place for 90-day check.

Learnings:
- Visual progress is a powerful engagement lever for casual users
- Power users (Tier 1) don't need additional motivation — they're already engaged
- Next hypothesis: test progress indicators in notifications for at-risk users
```

### 6.2 Searchable Fields

| Field | Purpose |
|---|---|
| Experiment ID | Unique reference |
| Surface area | home_feed, notifications, onboarding, pricing, content |
| Target segment | Who was tested |
| Primary metric | What was measured |
| Result | positive, negative, inconclusive |
| Effect size | Measured lift (%) |
| Learnings | Key takeaways |
| Follow-up experiments | What this experiment spawned |

---

## 7. Experimentation Culture

### 7.1 Operating Principles

1. **Every feature ships as an experiment.** No feature goes to 100% without measurement. Even "obvious" improvements are tested — our intuitions are frequently wrong.

2. **Negative results are valuable.** A well-run experiment that shows no effect is not a failure. It's information that prevents us from investing in the wrong thing. We celebrate learning, not just wins.

3. **Statistical rigor is non-negotiable.** We do not cherry-pick metrics, peek without sequential testing, or declare victory on subgroups. If the primary metric isn't significant, the experiment didn't work — regardless of what other metrics show.

4. **Speed over perfection.** A fast experiment with a 5% MDE beats a perfect experiment that takes 6 months. Run the test, learn, iterate. Compound small wins.

5. **Document everything.** Every experiment, including failures, goes in the repository. Future PMs will thank us for knowing that "we already tested larger fonts and it didn't help."

### 7.2 Experiment Velocity

| Quarter | Experiments Run | Shipped | Killed | Inconclusive |
|---|---|---|---|---|
| Q1 2024 | 12 | 4 (33%) | 5 (42%) | 3 (25%) |
| Q2 2024 | 28 | 9 (32%) | 12 (43%) | 7 (25%) |
| Q3 2024 | 41 | 14 (34%) | 18 (44%) | 9 (22%) |
| Q4 2024 | 52 | 19 (37%) | 20 (38%) | 13 (25%) |

**Observation:** Our ship rate is ~35%. This is healthy. A ship rate above 70% means you're only testing safe ideas. A ship rate below 20% means your hypotheses are poorly formed. 30-40% means we're taking real swings and learning from both wins and misses.

### 7.3 Cumulative Impact

The power of experimentation isn't any single test. It's the compound effect of dozens of small, validated improvements over time.

| Metric | Jan 2024 (Pre-Experimentation) | Dec 2024 (Post) | Compound Lift |
|---|---|---|---|
| Daily engagement rate | 22% | 28.2% | +28% |
| 7-day retention | 41% | 52% | +27% |
| 90-day retention | 32% | 51% | +59% |
| Session duration | 4.2 min | 5.7 min | +35% |
| ARPU | $8.40 | $11.20 | +33% |

No single experiment produced a 28% engagement lift. It was 52 experiments over 4 quarters, each contributing 0.5-3% lifts, compounding into transformative results.
