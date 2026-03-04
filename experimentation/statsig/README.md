# Statsig Experimentation Framework

Comprehensive A/B testing and feature flag management for the Engagement & Personalization Engine using Statsig.

## Overview

Statsig provides:
- **Feature Gates**: On/off switches with progressive rollout capabilities
- **A/B & Multivariate Testing**: Statistically rigorous experiment design and analysis
- **Real-time Bucketing**: Deterministic user assignment (same user = same variant)
- **Custom Event Logging**: Track conversions and engagement metrics
- **Segment Targeting**: Serve variants to specific user cohorts

## Installation

```bash
# Install Statsig Python SDK
pip install statsig-python

# Verify installation
python -c "import statsig; print(statsig.__version__)"
```

## Quick Start

```python
from experimentation.statsig.client import StatsigExperimentClient, StatsigUser

# Initialize client
client = StatsigExperimentClient(
    api_key="secret_key_from_statsig_console",
    environment="production"
)

# Create user context
user = StatsigUser(
    user_id="user_123",
    email="user@example.com",
    plan_tier="pro",
    region="US"
)

# Check feature gate
if client.check_gate(user, "enable_real_time_personalization"):
    # Serve personalized experience
    show_personalization()

# Get experiment assignment
exp = client.get_experiment(user, "recommendation_algorithm_v2")
if exp.group == "neural_embeddings":
    recommendations = get_neural_embeddings(user.user_id)
else:
    recommendations = get_collaborative_filtering(user.user_id)

# Log custom event
client.log_event(
    user=user,
    event_name="conversion_rate",
    value=1,
    metadata={"product": "premium_tier", "revenue": 99.99}
)

# Flush events
client.flush_events()
```

## How Experiments Work

### 1. Allocation (Who gets which variant?)

Experiments use deterministic **bucketing** to assign users:

```python
# Same user always gets same variant
for _ in range(3):
    exp = client.get_experiment(user, "recommendation_algorithm_v2")
    print(exp.group)  # Always outputs same variant
    # Output: neural_embeddings
    #         neural_embeddings
    #         neural_embeddings
```

Bucketing is based on:
- User ID (deterministic hash)
- Experiment ID
- Variant weights (50% control, 50% treatment)

### 2. Variants with Weights

```yaml
variants:
  control:
    weight: 0.50  # 50% of users
  treatment:
    weight: 0.50  # 50% of users
```

### 3. Exposure Logging

When you call `get_experiment()`, Statsig automatically logs an exposure event:
- User saw the experiment
- Which variant they were assigned
- Timestamp and user context

This exposure log is critical for statistical analysis to separate treatment effects from selection bias.

### 4. Metric Analysis

Statsig computes metrics by:
1. Segmenting users by variant assignment (using exposure log)
2. Filtering to events from users in the analysis period
3. Computing metric per variant
4. Computing p-value and confidence intervals using sequential analysis

## Creating New Experiments

### Step 1: Define in experiments.yaml

```yaml
my_new_experiment:
  name: "My Experiment Name"
  hypothesis: "Why do you think treatment will win?"
  variants:
    control:
      weight: 0.5
      description: "Control group"
      features:
        - some_flag: true
    treatment:
      weight: 0.5
      description: "Treatment group"
      features:
        - some_flag: false
        - new_feature: true
  primary_metric:
    name: "engagement_score"
    minimum_detectable_effect: 0.15
    baseline: 50.0
  duration_days: 14
  sample_size:
    minimum_sample_size: 1000
    power: 0.8
```

### Step 2: Update client.py

Add to `StatsigExperimentClient.EXPERIMENTS` dict.

### Step 3: Launch via Statsig Console

1. Go to Statsig Console (https://console.statsig.com)
2. Create new experiment with matching name
3. Configure rollout percentage (0% → 100%)
4. Monitor metrics in real-time

### Step 4: Implement in Code

```python
config = client.get_experiment(user, "my_new_experiment")

if config.group == "treatment":
    # New feature behavior
    result = new_algorithm(user_id)
else:
    # Control behavior
    result = old_algorithm(user_id)

client.log_event(
    user=user,
    event_name=config.experiment_name,
    value=result.engagement_score
)
```

## Interpreting Results

### P-value and Significance

- **p-value < 0.05**: Statistically significant (reject null hypothesis)
- **p-value >= 0.05**: Not significant (insufficient evidence of difference)

Example: p-value = 0.03
- 97% confidence treatment effect is real (not due to chance)

### Confidence Intervals

Statsig reports 95% confidence intervals for each metric:

```
Metric: Engagement Score
Control: 50.2 (95% CI: [49.8, 50.6])
Treatment: 52.1 (95% CI: [51.7, 52.5])
Difference: +1.9 points (p=0.002)
```

Interpretation: Treatment average is 1.9 points higher with 95% confidence the true difference is between 1.1-2.7 points.

### Sequential Testing

Statsig uses sequential analysis to allow early stopping:
- Continuously monitor results
- Stop early if clear winner emerges (p < 0.01)
- Reduce sample size requirements vs. fixed-horizon testing

## Feature Gates

Gates are on/off switches for gradual rollout.

### Progressive Rollout

```python
# Gradually increase percentage of users seeing feature
# Week 1: 10% rollout
# Week 2: 25% rollout
# Week 3: 50% rollout
# Week 4: 100% rollout

if client.check_gate(user, "enable_real_time_personalization"):
    # Feature is enabled for this user
    load_personalization_engine()
```

### Kill Switches

Use gates to disable features in emergencies:

```python
if not client.check_gate(user, "enable_ml_recommendations"):
    # ML pipeline is disabled - fallback to simpler algorithm
    return get_simple_recommendations(user_id)
```

## Best Practices

### 1. Plan Experiments in Advance

Write hypothesis and success criteria *before* launch:
- What metric indicates success?
- What magnitude improvement is meaningful?
- How long will you run?

### 2. Power Analysis

Statsig shows required sample size:
- 80% power is industry standard
- 95% significance level (0.05 alpha)
- Adjust based on baseline and MDE

### 3. Log Exposures Correctly

Always log exposures for users in treatment:
```python
config = client.get_experiment(user, "my_experiment")
# Exposure automatically logged by get_experiment()

# Only log metrics if user was exposed
if config.log_exposure:
    client.log_event(user, "my_metric", value)
```

### 4. Don't Peek Too Early

Continuous monitoring increases false positive rate:
- Run until minimum sample size reached
- Respect the pre-specified duration
- Use sequential testing, not raw p-values

### 5. Monitor Secondary Metrics

Track for negative side effects:
- If conversion increases but retention drops, investigate
- Metric conflicts indicate model misspecification

### 6. Clean Up Completed Experiments

Archive experiments after analysis complete:
```yaml
status: "completed"  # Mark in experiments.yaml
winner: "treatment"   # Document winner
lessons: "..."        # Record learnings
```

## Monitoring and Debugging

### Check Real-time Bucketing

```python
from experimentation.statsig.client import StatsigExperimentClient

client = StatsigExperimentClient(api_key="...", environment="prod")

user = StatsigUser(user_id="test_user_123")
config = client.get_experiment(user, "my_experiment")

print(f"Variant: {config.group}")
print(f"Is Treatment: {config.is_treatment}")
print(f"Config: {config.config}")
```

### Check Feature Gate Status

```python
gate_status = client.check_gate(user, "enable_feature_x")
print(f"Gate enabled for user: {gate_status}")

gate_config = client.get_gate_config("enable_feature_x")
print(f"Rollout percentage: {gate_config['initial_rollout_percentage']}%")
```

### Verify Events Are Logging

```python
# Events are queued locally
client.log_event(user, "test_event", value=123)

# Check queue size
print(f"Events in queue: {len(client.event_queue)}")

# Flush to Statsig
flushed = client.flush_events()
print(f"Flushed {flushed} events")
```

## Environment Variables

```bash
# .env
STATSIG_API_KEY=secret_key_from_console
STATSIG_ENVIRONMENT=production
STATSIG_LOG_LEVEL=INFO
```

## Troubleshooting

### Experiment Not Showing Results

1. Check exposure logging is enabled
2. Verify events are being flushed
3. Confirm users are in target audience
4. Check sample size vs. minimum required

### Gate Not Evaluating Correctly

1. Verify gate name matches Statsig console
2. Check rollout percentage (may be 0%)
3. Verify user attributes for targeting
4. Check gate prerequisites

### High Error Rate

1. Verify API key is valid
2. Check SDK initialization succeeded
3. Review logs for specific errors
4. Confirm network connectivity

## References

- [Statsig Documentation](https://docs.statsig.com)
- [Statsig Python SDK](https://github.com/statsig-io/python-sdk)
- [A/B Testing Best Practices](https://docs.statsig.com/guides/ab-testing)
- [Sequential Testing](https://docs.statsig.com/guides/sequential-testing)
