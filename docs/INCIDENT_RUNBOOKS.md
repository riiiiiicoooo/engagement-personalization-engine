# Engagement Personalization Engine — Incident Runbooks

**Last Updated:** March 2026
**Severity Levels:** P0 (experiment integrity broken, Kafka ordering lost), P1 (model accuracy regression, SLO breach), P2 (degraded performance)

---

## Incident Runbook 1: Sample Ratio Mismatch (SRM) — Invalid Experiment

**Likelihood:** Low (goal zero; comprehensive randomization testing)
**Severity:** P0 (experiment invalid; decisions based on fake data are dangerous)
**Detection Symptoms:** Chi-square test shows p-value < 0.05; experiment traffic split is off (45% vs. 55% instead of 50% vs. 50%)

### Detection

**Automated triggers:**
- Daily SRM check: Chi-square test on traffic split for all active experiments; p-value < 0.05 alerts
- Real-time monitoring: Traffic split drifts >5% from expected; alert after 24 hours at this level

**Manual triggers:**
- Analyst: "Variant B has higher traffic (55%) than expected (50%)"
- Engineer: "We changed randomization logic; new code must have introduced bias"

### Diagnosis (First 1 hour)

1. **Confirm SRM:**
   ```sql
   SELECT
     variant,
     COUNT(*) as user_count,
     COUNT(*) / SUM(COUNT(*)) OVER () as pct
   FROM experiment_assignments
   WHERE experiment_id = 'EXP_123'
   GROUP BY variant;

   -- Chi-square: (Obs - Exp)^2 / Exp
   -- If chi-square p-value < 0.05: SRM confirmed
   ```

2. **Identify root cause:**
   - **Time-based bias:** Was variant B launched later? Check timestamp distributions
   - **Device bias:** Is variant B heavily iOS, variant A Android? Check user agent distribution
   - **Geographic bias:** Is variant B concentrated in certain regions?
   - **User cohort bias:** Is variant B biased toward new vs. returning users?
   - **Code logic bug:** Did randomization code use biased random source?

3. **Scope the damage:**
   - How long has SRM been active? (Days? Weeks?)
   - How many users are in each variant? (More extreme ratio = more damage)
   - What metrics were being measured? (Biased split means metric estimates are biased)

### Remediation (First 2 hours)

**Immediate:**
1. **Pause the experiment:**
   - Stop assigning users to this experiment
   - Keep existing assignments (don't retroactively change)
   - Mark experiment as "PAUSED_SRM" in dashboard

2. **Diagnose the bias:**
   - Check assignment timestamps: Is there a time-based gradient?
   - Check device distribution: `SELECT variant, device, COUNT(*) FROM assignments GROUP BY variant, device`
   - Check geographic distribution (if available)

3. **Identify the code change:**
   - If randomization code changed recently: Rollback the change
   - If code hasn't changed: Investigate environment (did seeding change? is random source broken?)

**Within 24 hours:**
1. **Fix the randomization:**
   - If time-based: Ensure both variants launch simultaneously
   - If device-based: Verify randomization is independent of device
   - If code bug: Fix and test with new unit test

2. **Validate the fix:**
   - Re-run SRM test on new randomization
   - Confirm chi-square p-value > 0.05 (no SRM)

3. **Decide on experiment:**
   - If SRM was minor (traffic split 48% vs. 52%): May be able to salvage results with statistical correction
   - If SRM was major (45% vs. 55% or worse): Discard results; restart experiment

### Communication Template

**Internal (Slack #experiments):**
```
⚠️ P0: SRM Detected — Experiment [EXP_NAME] Invalid

Timeline:
- [TIME 1]: Experiment launched
- [TIME 2]: SRM detected by automated check
- [TIME 3]: Experiment paused

Scope:
- Traffic split: [A: X%, B: Y%] (expected 50% / 50%)
- SRM p-value: [VALUE] (threshold: < 0.05)
- Duration: [TIME]
- Users affected: [N]

Root cause:
- [ ] Time-based bias (variant B launched later)
- [ ] Device bias (iOS vs. Android)
- [ ] Code logic bug
- [ ] Other: [SPECIFY]

Actions:
- [x] Experiment paused
- [ ] Root cause fixed
- [ ] SRM test rerun and passed
- [ ] Experiment restarted or results discarded

Experiment status: INVALID (results will not be used for decision)
Next: Fix + restart experiment, or conclude with different variant assignment
```

---

## Incident Runbook 2: Model Accuracy Regression (NDCG Drop)

**Likelihood:** Medium (1-2x per quarter due to data drift, feature staleness, or model retraining issues)
**Severity:** P1 (recommendation quality degradation; user engagement may decline)
**Detection Symptoms:** Daily NDCG check shows score drops >0.05; users report "recommendations are worse"; engagement metrics decline

### Detection

**Automated triggers:**
- Daily NDCG check: NDCG < 0.70 (down from baseline 0.72)
- Recommendation relevance anomaly: Fewer users engaging with recommended content
- Feature staleness alert: Feature pipeline latency exceeds 15 min; features may be stale

**Manual triggers:**
- User complaints: "App recommendations are bad"
- Product dashboard: Engagement metrics down 2-3% (correlates with recommendation quality)
- Data scientist: "Latest model retraining failed; fell back to old model"

### Diagnosis (First 2 hours)

1. **Confirm accuracy drop:**
   ```sql
   SELECT
     DATE(created_at) as date,
     NDCG,
     NDCG - LAG(NDCG) OVER (ORDER BY created_at) as delta
   FROM daily_ndcg_scores
   ORDER BY date DESC LIMIT 30;
   ```
   Identify when NDCG dropped and by how much.

2. **Identify root cause:**
   - **Feature staleness:** Is feature pipeline latency > 10 min? Check `feature_freshness` metric
   - **Model retraining:** Did model training job fail or get delayed? Check Spark job logs
   - **Data distribution shift:** Are user behaviors changing? (Seasonal shift, user base composition change)
   - **Feature importance change:** Do feature weights make sense? (Did recent A/B test cause feature correlation shift?)
   - **Model code change:** Was model inference code changed? (Bug in feature extraction?)

3. **Assess user impact:**
   - Did engagement drop? (Click-through rate, completion rate)
   - Are specific user segments affected? (New users vs. existing; iOS vs. Android)
   - Is it a broad degradation or specific to certain content types?

### Remediation (First 4 hours)

**Immediate:**
1. **Rollback to previous model:**
   - Deploy previous known-good model version
   - Verify NDCG improves (should restore to ~0.72)

2. **Analyze the regression:**
   - Compare new model vs. old model feature importances
   - Check: Did feature staleness cause accuracy loss?
   - Check: Did data distribution change cause model to underperform?

**Within 24 hours:**
1. **Root cause deep-dive:**
   - If feature staleness: Optimize feature pipeline or reduce feature freshness requirements
   - If model retraining: Investigate what changed in training code or data
   - If data drift: May need to retrain on recent data or add online learning

2. **Fix:**
   - If feature staleness: Increase feature pipeline frequency (from hourly to every 30 min)
   - If model issue: Retrain with recent data; validate on holdout set before deploying
   - If data drift: Implement model monitoring (continuous evaluation) to catch drift earlier

3. **Prevent recurrence:**
   - Add pre-deployment validation: Test new model against holdout set; only deploy if NDCG > 0.71
   - Add feature freshness monitoring to alert if pipeline lags
   - Implement A/B test: New model vs. old model before full rollout

### Communication Template

**Internal (Slack #ml-team):**
```
🚨 P1: Model Accuracy Regression — NDCG Dropped

Timeline:
- [TIME 1]: Model degradation occurred
- [TIME 2]: Detected by automated check
- [TIME 3]: Previous model redeployed

Scope:
- NDCG: 0.72 → 0.68 (regression: -0.04)
- Duration: [TIME]
- Users affected: ALL (recommendation quality down for everyone)

Root cause:
- [ ] Feature staleness (pipeline latency > 10min)
- [ ] Model retraining failed
- [ ] Data distribution shift
- [ ] Code bug in model inference
- [ ] Other: [SPECIFY]

Actions:
- [x] Previous model redeployed (NDCG restored to 0.72)
- [ ] Root cause analysis
- [ ] Fix deployed (if not data drift)
- [ ] A/B test new model before full rollout

Engagement impact: [MONITOR] (should see improvement once model restored)
Next: A/B test fix in parallel; decide on rollout
```

---

## Incident Runbook 3: Kafka Message Ordering Loss (Event Stream Corruption)

**Likelihood:** Low (goal 99.9% ordering; should be rare)
**Severity:** P0 (experiment validity + feature engineering broken)
**Detection Symptoms:** Detected ordering violations (user event timestamps out of order); or analysis shows unusual patterns in experiment results

### Detection

**Automated triggers:**
- Daily ordering check: 1% sample of user event streams; timestamp inversions detected
- Kafka offset lag: Consumer lag spikes (indicates rebalancing/corruption)
- Churn prediction errors: Prediction scores anomalously high/low for users with ordering violations

**Manual triggers:**
- Data scientist: "User event stream looks corrupted; events out of time order"
- Kafka monitoring: Partition reassignment detected; may have lost ordering guarantees

### Diagnosis (First 30 minutes)

1. **Confirm ordering violation:**
   ```sql
   SELECT
     user_id,
     event_timestamp,
     LAG(event_timestamp) OVER (PARTITION BY user_id ORDER BY kafka_offset) as prev_timestamp
   FROM events
   WHERE prev_timestamp > event_timestamp
   LIMIT 100;
   ```
   Non-zero result confirms ordering violations exist.

2. **Scope the problem:**
   - How many users affected?
   - What time period are affected?
   - Are violations concentrated in certain Kafka partitions?

3. **Identify root cause:**
   - Check Kafka cluster logs: Did partition rebalancing occur?
   - Check Kafka broker logs: Any failures or restarts?
   - Check consumer logs: Did consumer crash and restart, causing offset reset?

### Remediation (First 2 hours)

**Immediate:**
1. **Stop affected consumers:**
   - Pause any streaming jobs consuming from affected partitions
   - Prevent further corruption from propagating to feature store

2. **Assess damage:**
   - Which experiments used events from affected partitions?
   - Which users' features are corrupted?
   - How long has ordering been broken?

**Within 24 hours:**
1. **Recover:**
   - Replay events from backup (if available) in correct order
   - Or: Restart from checkpoint before corruption; lose recent data but maintain ordering

2. **Root cause:**
   - Check Kafka broker health; restart any unhealthy brokers
   - Verify partition assignment is stable (not being rebalanced)
   - Check consumer group: Is it crashing and restarting? (Would reset offsets)

3. **Prevent recurrence:**
   - Add Kafka ordering validation: Continuous check that timestamps are monotonic
   - Alert on partition rebalancing: Need to be aware if rebalancing is degrading service
   - Backup strategy: Ensure backups capture event ordering (not just data)

### Communication Template

**Internal (Slack #data-platform):**
```
🚨 P0: Kafka Message Ordering Violation

Timeline:
- [TIME 1]: Ordering violation occurred (likely during Kafka rebalancing)
- [TIME 2]: Detected by monitoring
- [TIME 3]: Affected consumers paused

Scope:
- Ordering violations: [N] users
- Affected partitions: [LIST]
- Duration: [TIME PERIOD]
- Experiments affected: [LIST]
- Feature corruption: [ASSESS]

Root cause: [Kafka rebalancing / Broker failure / Consumer restart / Other]

Actions:
- [x] Affected consumers paused
- [ ] Partition health verified
- [ ] Events replayed from backup [if needed]
- [ ] Ordering validation enhanced

Impact on experiments: [SRM risk if affected experiment is active]
Impact on features: [Feature values may be incorrect for affected users]
Next: Full recovery status + impact assessment
```

