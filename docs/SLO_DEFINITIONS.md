# Engagement Personalization Engine — Service Level Objectives (SLOs)

**Last Updated:** March 2026
**Compliance Scope:** Experiment integrity (SRM detection), model reliability, feature freshness, Kafka ordering guarantees

---

## Error Budget Policy

Engagement Personalization operates on a **model performance budget** (not traditional availability budget). Unlike systems that optimize for uptime, EPE optimizes for recommendation quality and experiment validity. A brief 1-hour outage is less damaging than a 0.5% accuracy degradation that goes undetected for a week.

**SLO Categories:**
- **Model SLOs:** Recommendation accuracy, churn prediction accuracy, experiment SRM (zero tolerance for invalid experiments)
- **Operational SLOs:** API latency, system availability, Kafka message ordering (monthly error budgets)

---

## SLO 1: Recommendation Relevance (NDCG@10)

**Service:** `personalization-engine` (recommendation model + ranking)
**Definition:** Normalized Discounted Cumulative Gain (NDCG) metric comparing AI-ranked content against user-rated relevance. Higher ranked items should be items users actually engage with.

**Target:** ≥ 0.72 NDCG@10 (baseline: 0.72; target improvement: 0.75 by end of Q2 2026)

**Error Budget:** 1-2% accuracy degradation acceptable; if drops below 0.70, investigate

**Measurement:**
- Daily: Compare model rankings against user engagement (clicks, completions) from previous day
- Query: `NDCG@10 = SUM(relevance_i / log2(i+1)) / IDCG@10` for top 10 recommended items
- Sampling: 100% of recommendations; aggregated daily
- Source: `recommendation_events`, cross-reference with `engagement_events`

**Why This Target:**
- **User satisfaction:** NDCG 0.72 means ~70% of users find relevant content in top 10 recommendations; 0.75 means 75% find relevant content
- **Business impact:** Each 0.05 NDCG improvement ≈ +1-2% engagement lift (correlated through A/B tests)
- **Practical limit:** Pushing beyond 0.75 requires significantly more data or algorithmic complexity; diminishing returns
- **Baseline context:** Non-personalized ranking (sorting by popularity) achieves ~0.55 NDCG; our 0.72 represents 30% improvement over baseline

**Burn Rate Triggers:**
- **NDCG < 0.70:** Investigate model degradation; may indicate data drift or feature staleness
- **NDCG trending downward (>1pp per week):** Model retraining or feature recalibration needed
- **Recommendation latency spikes:** May indicate model serving latency issues affecting accuracy

**Mitigations:**
- Weekly retraining: Update recommendation model with latest user interaction data
- Feature monitoring: Track feature distributions; alert if unusual shift
- A/B testing: Validate model changes before full rollout
- Fallback ranking: If personalization unavailable, fall back to popularity-based ranking (0.55 NDCG acceptable)

---

## SLO 2: Churn Prediction Model Accuracy (AUC-ROC)

**Service:** `churn-prediction-model`
**Definition:** Area Under the Receiver Operating Characteristic Curve (AUC) for 14-day churn prediction. At threshold of 0.5, what % of true positives (churned users) are correctly identified vs. false positives (users predicted to churn but didn't)?

**Target:** ≥ 0.84 AUC (baseline: 0.84; model is well-calibrated)

**Error Budget:** None (accuracy is used to decide which users get intervention; poor accuracy wastes intervention budget)

**Measurement:**
- Monthly validation: Train model on 70% of users; validate on holdout 30%; calculate AUC
- Query: Plot ROC curve; calculate area under curve
- Source: `churn_predictions` vs. actual user activity 14 days later

**Why This Target:**
- **Intervention economics:** We have limited intervention budget (email/SMS slots); must target highest-churn-risk users. AUC 0.84 means we're ranking users by churn risk with 84% accuracy
- **Practical impact:** At 0.84 AUC, top 20% highest-risk users contain ~60% of actual churners; intervention spend is 3x efficient
- **Baseline:** Random prediction (0.5 AUC) vs. ours (0.84) is 68% improvement; further improvements yield diminishing returns

**Burn Rate Triggers:**
- **AUC < 0.80:** Model accuracy degrading; investigate data drift or missing features
- **AUC < 0.82:** Critical alert; retraining or model revision needed immediately
- **Prediction calibration off:** If model predicts 20% churn but actual churn is 10%, recalibrate thresholds

**Mitigations:**
- Monthly retraining: Update features with latest user behavior
- Feature engineering: Add new behavioral signals (session depth, content completion, streak length)
- Threshold tuning: Adjust decision threshold based on intervention capacity vs. risk

---

## SLO 3: Experiment Integrity (Sample Ratio Mismatch Detection)

**Service:** `experiment-analysis-pipeline`
**Definition:** Percentage of experiments where traffic is randomly split per design (A: 50%, B: 50%) without systematic bias. If ratio is off (A: 45%, B: 55%), experiment is invalid (SRM = Sample Ratio Mismatch).

**Target:** 100% of experiments valid (SRM incidents = 0)

**Error Budget:** None (invalid experiments waste time and money)

**Measurement:**
- Per-experiment: Chi-square test comparing observed traffic split vs. expected split
- Alert threshold: p-value < 0.05 indicates SRM (reject experiment)
- Sampling: 100% of active experiments; real-time monitoring
- Source: `experiment_assignments`, compare user counts per variant

**Why This Target:**
- **Statistical validity:** If traffic split is biased (45% vs. 55%), experiment results are biased. Metric lifts measured in SRM experiments are false signals
- **Cost of SRM:** SRM experiment wastes ~2 weeks of time (while running, then investigating why results seem off). At 52 experiments/quarter, 1 SRM/quarter = 4% of experiment capacity wasted
- **Zero tolerance:** Every active experiment should satisfy SRM constraint; no exceptions

**Burn Rate Triggers:**
- **1+ SRM detected in active experiments:** Pause the experiment immediately; investigate randomization logic
- **SRM pattern detected:** (e.g., "every time variant B is favored, we see SRM") — investigate code logic

**Mitigations:**
- Randomization validation: On first user exposure, verify they're assigned randomly (no correlation with user attributes)
- Real-time SRM monitoring: Check daily; alert if p-value crosses threshold
- Debugging: When SRM occurs, check for: time-based bias (variant B launched later), device bias (iOS vs. Android bias), geographic bias

---

## SLO 4: Feature Freshness (Data Pipeline Latency)

**Service:** `feature-pipeline` (Kafka → Spark → FeatureStore)
**Definition:** Time from user event (content completion, engagement) to feature availability in personalization model. Target: <10 minutes (p95).

**Target:** 95% of features available within 10 minutes of user action

**Error Budget:** 36 hours/month (at 100K feature updates/day baseline)

**Measurement:**
- Query: `(FEATURES_FRESH_WITHIN_10MIN) / TOTAL_FEATURE_UPDATES`
- Sampling: 100% of feature updates; real-time latency measurement
- Source: `event_timestamp` → `feature_available_timestamp`

**Why This Target:**
- **User experience:** If user completes content at 2:00 PM and we don't learn they completed it until 2:15 PM, next recommendation at 2:05 PM won't benefit from that signal
- **Practical latency breakdown:**
  - Event generated: Immediate (0s)
  - Event written to Kafka: ~100ms
  - Kafka batching: ~1 min (batch accumulates events)
  - Spark job processes batch: ~2 min
  - Features written to FeatureStore: ~1 min
  - Features loaded into model: ~1 min
  - Total: ~5 min baseline; 10 min target allows for queuing, delays

**Burn Rate Triggers:**
- **p95 latency > 15 min:** Watch alert; feature pipeline slower than expected
- **p95 latency > 20 min:** Investigate; may indicate Spark job backing up or FeatureStore unavailable
- **Kafka lag > 30 min:** Critical alert; event ingestion is stuck

**Mitigations:**
- Stream processing: Use Kafka Streams for real-time (vs. batch Spark) for most frequent features
- Feature caching: Cache recent feature values in Redis; serve stale values if pipeline slow
- Sampling: During high-load periods, sample events (update 90% of features) to maintain latency

---

## SLO 5: API Latency (Personalization Endpoint Responsiveness)

**Service:** `/recommend` endpoint
**Definition:** Percentage of personalization API requests where response received within 150ms (p95 latency).

**Target:** 95% ≤ 150ms (p95)

**Error Budget:** 36 hours/month (at 1M requests/day baseline)

**Measurement:**
- Query: `(REQUESTS_COMPLETED_WITHIN_150MS) / TOTAL_REQUESTS`
- Source: API request latency metrics (application instrumentation)

**Why This Target:**
- **User perception:** Mobile app users expect sub-200ms response time; at 150ms p95, 95% of users see instant (sub-200ms) response
- **Latency breakdown:**
  - Feature lookup from FeatureStore: ~30ms
  - Model inference (on-device or cached): ~50ms
  - Ranking/sorting: ~20ms
  - Serialization: ~20ms
  - Network/overhead: ~30ms
  - Total: ~150ms baseline

**Burn Rate Triggers:**
- **p95 latency > 200ms:** High burn; model serving may be slow or feature cache misses increasing
- **p99 latency > 500ms:** Critical; user experience degrading
- **Error rate > 0.5%:** Check exception types; timeouts or dependency failures

**Mitigations:**
- Feature caching: Hot features cached in Redis; 80%+ hit rate expected
- Model serving: On-device inference (TensorFlow Lite) or cached responses; minimize latency
- Fallback ranking: If personalization slow, use cached popularity-based ranking
- Load shedding: During traffic spikes, shed low-priority requests (experimental groups) to maintain SLO for majority

---

## SLO 6: Kafka Message Ordering (Experiment Integrity)

**Service:** `kafka-message-broker` (experiment assignments, engagement events)
**Definition:** Percentage of user events where Kafka message ordering is preserved. For a single user, events should arrive in chronological order (no out-of-order messages).

**Target:** 99.9% of user event streams maintain order

**Error Budget:** None (out-of-order events break experiment analysis and churn predictions)

**Measurement:**
- Sampling: 1% of user event streams; verify no timestamp inversions
- Alert threshold: If >0.1% of streams have ordering violations, investigate
- Source: Kafka topic partition logs

**Why This Target:**
- **Experiment analysis:** If user assigned to variant A at T1, then variant B at T2, but messages arrive as T2 then T1, analysis is wrong
- **Feature engineering:** Churn prediction assumes events in chronological order; if order is wrong, temporal features are wrong
- **Practical reality:** Kafka with single partition per user guarantees ordering; but if partitions are rebalanced, ordering can be lost

**Burn Rate Triggers:**
- **Ordering violations > 0.1%:** Alert on-call; investigate Kafka rebalancing or partition reassignment
- **Any ordering violation in critical user cohort:** Manual fix; may need to replay events

**Mitigations:**
- Single partition per user: Ensure all user events go to same Kafka partition
- Monitoring: Daily check that partitions are stable (not being rebalanced)
- Recovery: If rebalancing occurs, replay events in correct order

