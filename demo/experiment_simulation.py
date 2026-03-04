#!/usr/bin/env python3
"""
Experiment Simulation Script
=============================

A complete A/B test lifecycle simulation demonstrating:
1. Experiment definition (variants, metrics, guardrails)
2. User assignment (deterministic hashing for uniformity)
3. 28-day metric collection with true treatment effect
4. Sequential analysis with O'Brien-Fleming boundaries
5. Early stopping detection
6. Sample Ratio Mismatch (SRM) violation detection
7. Guardrail metric degradation and auto-stopping

This demonstrates realistic experiment lifecycle including:
- Day-by-day metric collection
- Statistical boundary checking for early stopping
- SRM violation on day 14
- Guardrail breach on day 21
- Proper experiment conclusion

Run with: python demo/experiment_simulation.py
"""

import hashlib
import math
import random


# =============================================================================
# SECTION 1: SETUP & EXPERIMENT DEFINITION
# =============================================================================
print("=" * 90)
print("A/B TEST LIFECYCLE SIMULATION")
print("=" * 90)
print()

print("SECTION 1: EXPERIMENT DEFINITION")
print("-" * 90)

# Experiment configuration
EXPERIMENT_ID = "exp-042-progress-indicators"
EXPERIMENT_NAME = "Progress Indicators on Home Feed"
HYPOTHESIS = "Adding progress indicators will increase content completion rate by 8%"
BASELINE_COMPLETION_RATE = 0.45
TREATMENT_EFFECT = 0.08  # 8% relative lift

# User assignment
TOTAL_USERS = 100000
CONTROL_PROPORTION = 0.50
TREATMENT_PROPORTION = 0.50
LONG_TERM_HOLDOUT_PCT = 0.05  # 5% of users in holdout group

print(f"Experiment: {EXPERIMENT_NAME}")
print(f"ID: {EXPERIMENT_ID}")
print(f"Hypothesis: {HYPOTHESIS}")
print()
print(f"Population: {TOTAL_USERS:,} users")
print(f"  Control: {CONTROL_PROPORTION*100:.0f}% ({int(TOTAL_USERS * CONTROL_PROPORTION):,} users)")
print(f"  Treatment: {TREATMENT_PROPORTION*100:.0f}% ({int(TOTAL_USERS * TREATMENT_PROPORTION):,} users)")
print(f"  Long-term holdout: {LONG_TERM_HOLDOUT_PCT*100:.0f}%")
print()
print(f"Primary metric: content_completion_rate")
print(f"  Baseline: {BASELINE_COMPLETION_RATE:.1%}")
print(f"  Expected treatment: {BASELINE_COMPLETION_RATE * (1 + TREATMENT_EFFECT):.1%} (+{TREATMENT_EFFECT:.1%})")
print()
print(f"Guardrails:")
print(f"  - session_duration: must not decrease >10%")
print(f"  - crash_rate: must not increase >0.5%")
print()


# =============================================================================
# SECTION 2: USER ASSIGNMENT
# =============================================================================
print("SECTION 2: USER ASSIGNMENT (Deterministic Hashing)")
print("-" * 90)

def compute_bucket(user_id, experiment_id):
    """Compute deterministic bucket (0-99) for user assignment."""
    hash_input = f"{user_id}:{experiment_id}".encode('utf-8')
    hash_digest = hashlib.sha256(hash_input).hexdigest()
    bucket_value = int(hash_digest[:8], 16)
    return bucket_value % 100

def assign_user(user_id, experiment_id):
    """Assign user to control or treatment."""
    bucket = compute_bucket(user_id, experiment_id)

    # Long-term holdout
    if bucket < LONG_TERM_HOLDOUT_PCT * 100:
        return None  # User is in holdout, not assigned

    # Control vs treatment
    if bucket < CONTROL_PROPORTION * 100:
        return "control"
    else:
        return "treatment"

# Assign users
assignments = {}
assignment_counts = {'control': 0, 'treatment': 0, 'holdout': 0}

for user_id in range(TOTAL_USERS):
    variant = assign_user(f"user_{user_id}", EXPERIMENT_ID)
    if variant:
        assignments[user_id] = variant
        assignment_counts[variant] += 1
    else:
        assignment_counts['holdout'] += 1

eligible_users = TOTAL_USERS - assignment_counts['holdout']

print("Assignment Distribution:")
print(f"  Control: {assignment_counts['control']:>7,} users ({assignment_counts['control']/eligible_users*100:>5.1f}% of eligible)")
print(f"  Treatment: {assignment_counts['treatment']:>7,} users ({assignment_counts['treatment']/eligible_users*100:>5.1f}% of eligible)")
print(f"  Holdout: {assignment_counts['holdout']:>7,} users ({assignment_counts['holdout']/TOTAL_USERS*100:>5.1f}% total)")
print()

# Validate uniformity
buckets = [0] * 100
for i in range(10000):
    bucket = compute_bucket(f"test_user_{i}", EXPERIMENT_ID)
    buckets[bucket] += 1

bucket_mean = sum(buckets) / len(buckets)
bucket_stdev = math.sqrt(sum((b - bucket_mean) ** 2 for b in buckets) / len(buckets))
bucket_cv = bucket_stdev / bucket_mean

print("Hash Distribution Validation (10K users):")
print(f"  Mean bucket: {bucket_mean:.1f}")
print(f"  Std dev: {bucket_stdev:.2f}")
print(f"  Coefficient of variation: {bucket_cv:.4f}")
print(f"  Status: {'OK' if bucket_cv < 0.05 else 'SKEWED'} (expect < 0.05)")
print()


# =============================================================================
# SECTION 3: METRIC COLLECTION (28 DAYS)
# =============================================================================
print("SECTION 3: METRIC COLLECTION (28 DAYS)")
print("-" * 90)
print()

# Simulate daily metric collection
random.seed(42)

# Initialize metrics by day
daily_metrics = {}

# Control group metrics
control_base_completion = BASELINE_COMPLETION_RATE
control_base_session_duration = 4.2
control_base_crash_rate = 0.005

# Treatment group metrics (with +8% lift)
treatment_completion = BASELINE_COMPLETION_RATE * (1 + TREATMENT_EFFECT)
treatment_session_duration = control_base_session_duration
treatment_crash_rate = control_base_crash_rate

# Add some variance across days
daily_variance_factor = 0.98  # 98-102% of base

# Day 0: Initialize
day_summary = {
    'day': 0,
    'control': {
        'users': 0,
        'completions': 0,
        'completion_rate': 0,
        'sessions': 0,
        'total_duration': 0,
        'avg_session_duration': 0,
        'crashes': 0,
        'crash_rate': 0
    },
    'treatment': {
        'users': 0,
        'completions': 0,
        'completion_rate': 0,
        'sessions': 0,
        'total_duration': 0,
        'avg_session_duration': 0,
        'crashes': 0,
        'crash_rate': 0
    }
}

print(f"{'Day':<5s} {'Control Completion':<22s} {'Treatment Completion':<22s} "
      f"{'Lift':<10s} {'Status':<30s}")
print("-" * 90)

all_days_data = []

for day in range(1, 29):
    # Daily variance
    variance = random.uniform(daily_variance_factor, 1.0 / daily_variance_factor)

    # Control metrics
    daily_control_users = int(eligible_users * 0.5 / 28)  # ~1/28 of control per day
    daily_control_completions = int(daily_control_users * control_base_completion * variance)
    control_completion_rate = daily_control_completions / daily_control_users if daily_control_users > 0 else 0

    daily_control_sessions = daily_control_users
    daily_control_duration = int(daily_control_sessions * control_base_session_duration * variance)
    control_session_duration = daily_control_duration / daily_control_sessions if daily_control_sessions > 0 else 0

    daily_control_crashes = int(daily_control_users * control_base_crash_rate)
    control_crash_rate = daily_control_crashes / daily_control_users if daily_control_users > 0 else 0

    # Treatment metrics (with true effect)
    daily_treatment_users = int(eligible_users * 0.5 / 28)  # ~1/28 of treatment per day
    daily_treatment_completions = int(daily_treatment_users * treatment_completion * variance)
    treatment_completion_rate = daily_treatment_completions / daily_treatment_users if daily_treatment_users > 0 else 0

    daily_treatment_sessions = daily_treatment_users
    daily_treatment_duration = int(daily_treatment_sessions * treatment_session_duration * variance)
    treatment_session_duration = daily_treatment_duration / daily_treatment_sessions if daily_treatment_sessions > 0 else 0

    daily_treatment_crashes = int(daily_treatment_users * treatment_crash_rate)
    treatment_crash_rate = daily_treatment_crashes / daily_treatment_users if daily_treatment_users > 0 else 0

    # Simulate SRM violation on day 14
    if day == 14:
        # Corrupt treatment sample ratio
        daily_treatment_users = int(daily_treatment_users * 0.85)  # 15% drop in treatment

    # Simulate guardrail breach on day 21
    if day >= 21:
        treatment_crash_rate = min(0.015, treatment_crash_rate * 1.8)  # 3x baseline

    # Calculate lift
    lift_pct = ((treatment_completion_rate - control_completion_rate) / control_completion_rate * 100
                if control_completion_rate > 0 else 0)

    # Accumulate data
    day_summary['day'] = day
    day_summary['control']['users'] += daily_control_users
    day_summary['control']['completions'] += daily_control_completions
    day_summary['control']['sessions'] += daily_control_sessions
    day_summary['control']['total_duration'] += daily_control_duration
    day_summary['control']['crashes'] += daily_control_crashes

    day_summary['treatment']['users'] += daily_treatment_users
    day_summary['treatment']['completions'] += daily_treatment_completions
    day_summary['treatment']['sessions'] += daily_treatment_sessions
    day_summary['treatment']['total_duration'] += daily_treatment_duration
    day_summary['treatment']['crashes'] += daily_treatment_crashes

    # Calculate cumulative rates
    day_summary['control']['completion_rate'] = (day_summary['control']['completions'] /
                                                 day_summary['control']['users']
                                                 if day_summary['control']['users'] > 0 else 0)
    day_summary['control']['avg_session_duration'] = (day_summary['control']['total_duration'] /
                                                      day_summary['control']['sessions']
                                                      if day_summary['control']['sessions'] > 0 else 0)
    day_summary['control']['crash_rate'] = (day_summary['control']['crashes'] /
                                            day_summary['control']['users']
                                            if day_summary['control']['users'] > 0 else 0)

    day_summary['treatment']['completion_rate'] = (day_summary['treatment']['completions'] /
                                                   day_summary['treatment']['users']
                                                   if day_summary['treatment']['users'] > 0 else 0)
    day_summary['treatment']['avg_session_duration'] = (day_summary['treatment']['total_duration'] /
                                                        day_summary['treatment']['sessions']
                                                        if day_summary['treatment']['sessions'] > 0 else 0)
    day_summary['treatment']['crash_rate'] = (day_summary['treatment']['crashes'] /
                                              day_summary['treatment']['users']
                                              if day_summary['treatment']['users'] > 0 else 0)

    cumulative_lift = ((day_summary['treatment']['completion_rate'] -
                       day_summary['control']['completion_rate']) /
                       day_summary['control']['completion_rate'] * 100
                       if day_summary['control']['completion_rate'] > 0 else 0)

    # Determine status
    status = "Collecting"
    if day == 14:
        status = "⚠ SRM DETECTED on day 14"
    if day >= 21:
        status = "⚠ GUARDRAIL BREACH (crash)"

    all_days_data.append({
        'day': day,
        'control_users': day_summary['control']['users'],
        'treatment_users': day_summary['treatment']['users'],
        'control_rate': day_summary['control']['completion_rate'],
        'treatment_rate': day_summary['treatment']['completion_rate'],
        'lift': cumulative_lift,
        'control_duration': day_summary['control']['avg_session_duration'],
        'treatment_duration': day_summary['treatment']['avg_session_duration'],
        'control_crash': day_summary['control']['crash_rate'],
        'treatment_crash': day_summary['treatment']['crash_rate']
    })

    # Print every 3 days
    if day % 3 == 0 or day == 1 or day == 14 or day == 21 or day == 28:
        print(f"{day:<5d} {day_summary['control']['completion_rate']:<22.1%} "
              f"{day_summary['treatment']['completion_rate']:<22.1%} "
              f"{cumulative_lift:+.1f}% {status:<30s}")

print()

# Final metrics summary
print("Final Cumulative Results (Day 28):")
print(f"  Control completion rate: {day_summary['control']['completion_rate']:.1%} ({day_summary['control']['users']:,} users)")
print(f"  Treatment completion rate: {day_summary['treatment']['completion_rate']:.1%} ({day_summary['treatment']['users']:,} users)")
print(f"  Lift: {cumulative_lift:+.1%}")
print()


# =============================================================================
# SECTION 4: STATISTICAL ANALYSIS
# =============================================================================
print("SECTION 4: SEQUENTIAL ANALYSIS (O'Brien-Fleming Boundaries)")
print("-" * 90)
print()

def normal_cdf(z):
    """Standard normal CDF approximation."""
    if z < -8:
        return 0.0
    if z > 8:
        return 1.0
    a1, a2, a3, a4, a5 = (0.254829592, -0.284496736, 1.421413741,
                          -1.453152027, 1.061405429)
    p = 0.3275911
    sign = 1 if z >= 0 else -1
    z = abs(z) / math.sqrt(2)
    t = 1.0 / (1.0 + p * z)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-z * z)
    return 0.5 * (1.0 + sign * y)

def normal_ppf(p):
    """Inverse normal CDF approximation."""
    if p <= 0:
        return -8.0
    if p >= 1:
        return 8.0
    if p == 0.5:
        return 0.0

    t = math.sqrt(-2 * math.log(min(p, 1 - p)))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    result = t - (c0 + c1 * t + c2 * t * t) / (1 + d1 * t + d2 * t * t + d3 * t * t * t)

    return result if p > 0.5 else -result

def analyze_proportion(control_success, control_total, treatment_success, treatment_total, alpha=0.05):
    """Two-sample z-test for proportions."""
    p_control = control_success / control_total if control_total > 0 else 0
    p_treatment = treatment_success / treatment_total if treatment_total > 0 else 0

    p_pooled = ((control_success + treatment_success) /
                (control_total + treatment_total))

    se = math.sqrt(p_pooled * (1 - p_pooled) *
                   (1/control_total + 1/treatment_total))

    if se == 0:
        return 1.0

    z = (p_treatment - p_control) / se
    p_value = 2 * (1 - normal_cdf(abs(z)))

    return p_value

def sequential_boundary(information_fraction, alpha=0.05):
    """O'Brien-Fleming spending function boundary."""
    if information_fraction <= 0:
        return 0.0001

    z_alpha = normal_ppf(1 - alpha / 2)
    z_boundary = z_alpha / math.sqrt(information_fraction)
    p_boundary = 2 * (1 - normal_cdf(z_boundary))

    return p_boundary

# Analyze at planned interims: 25%, 50%, 75%, 100%
interim_points = [7, 14, 21, 28]

print(f"{'Interim':<10s} {'Info Frac':<12s} {'Boundary':<12s} {'P-value':<12s} {'Decision':<25s}")
print("-" * 90)

for interim_day in interim_points:
    day_data = all_days_data[interim_day - 1]

    information_fraction = interim_day / 28.0

    control_users = day_data['control_users']
    control_completions = int(day_data['control_rate'] * control_users)
    treatment_users = day_data['treatment_users']
    treatment_completions = int(day_data['treatment_rate'] * treatment_users)

    p_value = analyze_proportion(control_completions, control_users,
                                treatment_completions, treatment_users)

    boundary = sequential_boundary(information_fraction)

    if p_value < boundary:
        decision = f"✓ SIGNIFICANT (p < boundary)"
    else:
        decision = f"Continue running"

    print(f"Day {interim_day:<5d} {information_fraction:<12.0%} {boundary:<12.6f} "
          f"{p_value:<12.6f} {decision:<25s}")

print()


# =============================================================================
# SECTION 5: SRM DETECTION
# =============================================================================
print("SECTION 5: SAMPLE RATIO MISMATCH (SRM) DETECTION")
print("-" * 90)
print()

def chi_squared_p_value(chi_sq, df):
    """Approximate chi-squared p-value."""
    if df <= 0 or chi_sq <= 0:
        return 1.0
    z = ((chi_sq / df) ** (1/3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
    return 1 - normal_cdf(z)

def check_srm(observed_counts, expected_ratios, threshold=0.001):
    """Detect Sample Ratio Mismatch using chi-squared test."""
    total = sum(observed_counts.values())
    chi_squared = 0

    for variant, observed in observed_counts.items():
        expected = total * expected_ratios.get(variant, 0.5)
        if expected > 0:
            chi_squared += (observed - expected) ** 2 / expected

    df = len(observed_counts) - 1
    p_value = chi_squared_p_value(chi_squared, df)

    srm_detected = p_value < threshold

    return {
        'chi_squared': round(chi_squared, 4),
        'p_value': round(p_value, 6),
        'srm_detected': srm_detected,
        'expected': {v: round(total * r) for v, r in expected_ratios.items()}
    }

# Check SRM at day 14 (where we simulated violation)
day_14_data = all_days_data[13]
srm_result = check_srm(
    {'control': day_14_data['control_users'], 'treatment': day_14_data['treatment_users']},
    {'control': 0.5, 'treatment': 0.5}
)

print("Day 14 Sample Ratio Check:")
print(f"  Observed: control={day_14_data['control_users']:,}, treatment={day_14_data['treatment_users']:,}")
print(f"  Expected: control={srm_result['expected']['control']:,}, treatment={srm_result['expected']['treatment']:,}")
print(f"  Chi-squared: {srm_result['chi_squared']:.4f}")
print(f"  P-value: {srm_result['p_value']:.6f}")
print(f"  Status: {'❌ SRM DETECTED - PAUSE EXPERIMENT' if srm_result['srm_detected'] else 'OK'}")
print()
print("  Possible causes:")
print("    - Assignment logic bug (hash not distributing evenly)")
print("    - Bot traffic concentrated in one variant")
print("    - Client-side filtering removing one variant users")
print("    - Data logging pipeline issue")
print()


# =============================================================================
# SECTION 6: GUARDRAIL MONITORING
# =============================================================================
print("SECTION 6: GUARDRAIL METRIC DEGRADATION & AUTO-STOP")
print("-" * 90)
print()

# Analyze guardrails
print("Guardrail 1: Session Duration (must not decrease >10%)")

day_21_data = all_days_data[20]
duration_diff_pct = ((day_21_data['treatment_duration'] - day_21_data['control_duration']) /
                     day_21_data['control_duration'] * 100)

print(f"  Control avg duration: {day_21_data['control_duration']:.2f} min")
print(f"  Treatment avg duration: {day_21_data['treatment_duration']:.2f} min")
print(f"  Difference: {duration_diff_pct:+.1f}%")
print(f"  Threshold: -10.0%")
print(f"  Status: {'OK' if duration_diff_pct >= -10.0 else '❌ BREACHED'}")
print()

print("Guardrail 2: Crash Rate (must not increase >0.5%)")

baseline_crash = day_21_data['control_crash']
treatment_crash = day_21_data['treatment_crash']
crash_diff_pct = (treatment_crash - baseline_crash) * 100

print(f"  Control crash rate: {baseline_crash:.2%}")
print(f"  Treatment crash rate: {treatment_crash:.2%}")
print(f"  Absolute difference: {crash_diff_pct:+.2f}%")
print(f"  Threshold: +0.5%")
print(f"  Status: {'❌ BREACHED - AUTO-STOP EXPERIMENT' if crash_diff_pct > 0.5 else 'OK'}")
print()

if crash_diff_pct > 0.5:
    print("ACTION: Experiment auto-stopped due to guardrail breach")
    print("  - Rollback treatment to 0% of users")
    print("  - Alert product and engineering teams")
    print("  - Begin incident investigation")
print()


# =============================================================================
# SECTION 7: FINAL DECISION
# =============================================================================
print("SECTION 7: EXPERIMENT CONCLUSION & DECISION")
print("-" * 90)
print()

# Final analysis
final_day = all_days_data[-1]

final_p_value = analyze_proportion(
    int(final_day['control_rate'] * final_day['control_users']),
    final_day['control_users'],
    int(final_day['treatment_rate'] * final_day['treatment_users']),
    final_day['treatment_users']
)

final_boundary = sequential_boundary(1.0)

print(f"Experiment Duration: 28 days")
print(f"Final Sample Size: {final_day['control_users']:,} (control) + {final_day['treatment_users']:,} (treatment)")
print()
print(f"Primary Metric Results:")
print(f"  Control completion rate: {final_day['control_rate']:.2%}")
print(f"  Treatment completion rate: {final_day['treatment_rate']:.2%}")
print(f"  Absolute lift: {(final_day['treatment_rate'] - final_day['control_rate'])*100:+.2f} pp")
print(f"  Relative lift: {final_day['lift']:+.1f}%")
print()
print(f"Statistical Significance:")
print(f"  P-value: {final_p_value:.6f}")
print(f"  Significance level (α): 0.05")
print(f"  Result: {'✓ SIGNIFICANT' if final_p_value < 0.05 else '✗ NOT SIGNIFICANT'}")
print()

# Determine decision
decision = "FAIL TO REJECT"
if final_p_value < final_boundary:
    decision = "SHIP"
elif crash_diff_pct > 0.5:
    decision = "KILL"
elif srm_result['srm_detected']:
    decision = "HOLD (investigate SRM)"
else:
    decision = "ITERATE"

print(f"Experiment Decision: {decision}")
print()

if decision == "SHIP":
    print("Recommendation:")
    print(f"  - Effect size is meaningful (+{final_day['lift']:.1f}%)")
    print(f"  - Guardrails are clean")
    print(f"  - No SRM detected")
    print(f"  - Proceed with full rollout")
elif decision == "KILL":
    print("Recommendation:")
    print(f"  - Guardrail metric (crash rate) degraded")
    print(f"  - User harm detected")
    print(f"  - Revert to control experience")
    print(f"  - Debug before next iteration")
elif decision == "ITERATE":
    print("Recommendation:")
    print(f"  - Directional positive (+{final_day['lift']:.1f}%)")
    print(f"  - Not statistically significant")
    print(f"  - Refine variant and retest with larger sample")

print()

print("=" * 90)
print("SIMULATION COMPLETE")
print("=" * 90)
