/**
 * PostHog Experiments Configuration
 *
 * Defines experiment configurations, targeting rules, and statistical parameters
 * for A/B testing across the personalization engine.
 *
 * This module demonstrates:
 * - Hypothesis-driven experiment design
 * - Statistically rigorous metrics and sample size calculations
 * - Guardrail metrics to protect core user experience
 * - Feature flag integration for progressive rollout
 * - Segment targeting for experiment stratification
 */

/**
 * Statistical Configuration for Experiments
 */
export interface StatisticalConfig {
  significanceLevel: number; // Alpha: 0.05 = 95% confidence
  power: number; // Beta: 0.8 = 80% power (20% type II error)
  minSampleSize: number; // Minimum users per variant
  samplingUnit: 'user' | 'session' | 'event'; // What granularity we randomize on
  testType: 'two_tailed' | 'one_tailed'; // Two-tailed for both directions, one-tailed for directional
}

/**
 * Metric Definition for Experiment Analysis
 */
export interface MetricDefinition {
  name: string;
  eventNames: string[];
  aggregationType: 'sum' | 'mean' | 'count' | 'ratio';
  unitType: 'user' | 'session' | 'event';
  description: string;
  direction: 'increase' | 'decrease';
}

/**
 * Guardrail Metric Definition
 *
 * Metrics that we monitor to ensure experiment doesn't harm user experience
 */
export interface GuardrailMetric extends MetricDefinition {
  upperBound?: number; // Max increase we tolerate (e.g., 0.05 = 5% increase)
  lowerBound?: number; // Min decrease we tolerate (e.g., -0.05 = 5% decrease)
  autoStopThreshold?: number; // Statistical threshold for auto-stopping
}

/**
 * Feature Flag Targeting Rules
 *
 * Defines who sees which variant during rollout
 */
export interface TargetingRule {
  type: 'percentage' | 'segment' | 'user_id' | 'cohort';
  value: string | number;
  variantMap: Record<string, number>; // Map variant to rollout %
}

/**
 * Experiment Instance Configuration
 */
export interface ExperimentInstance {
  experimentId: string;
  name: string;
  description: string;
  hypothesis: string;

  // Variants
  variants: {
    control: string;
    treatment: string[];
  };

  // Metrics
  primaryMetrics: MetricDefinition[];
  guardrailMetrics: GuardrailMetric[];
  secondaryMetrics?: MetricDefinition[];

  // Statistical configuration
  stats: StatisticalConfig;

  // Targeting and rollout
  targetSegments: string[]; // Empty = all users
  rolloutPercentage: number; // 0-100, start at 1-5% for monitoring
  startDate: Date;
  endDate?: Date;
  progressiveRollout?: {
    phase1Percentage: number; // Initial rollout
    phase1Duration: number; // Days
    phase2Percentage: number;
    phase2Duration: number;
    phase3Percentage: number;
  };

  // Monitoring
  monitoringInterval: number; // Hours between checks
  checkGuar drails: boolean;
  autoStopOnGuardrailBreach: boolean;

  // Analysis parameters
  noveltyDetectionWindow?: number; // Days to check if effect decays
  persistenceHoldout?: number; // % holdout for long-term measurement
  minRuntimeDays?: number; // Minimum days to run before analyzing
}

// ============================================================================
// DEFINED EXPERIMENTS
// ============================================================================

/**
 * EXPERIMENT 1: Notification Frequency Optimization
 *
 * Test: How does notification frequency impact retention and engagement?
 *
 * Hypothesis:
 * Users who receive notifications 3x per week will have:
 * - Higher 7-day retention vs weekly users
 * - Higher engagement vs daily users (less fatigue)
 * - Lower opt-out rate vs daily users
 *
 * Rationale:
 * Current: All active users get daily notifications
 * Problem: 34% opt-out rate, complaint rate increasing
 * Solution: Test frequency tuning to maximize retention without fatigue
 */
export const NOTIFICATION_FREQUENCY_EXPERIMENT: ExperimentInstance = {
  experimentId: 'notification_frequency_test',
  name: 'Notification Frequency Optimization',
  description: 'Optimize notification frequency to balance engagement and opt-out rates',
  hypothesis:
    'Users who receive notifications 3x per week will have higher 7-day retention (5% lift) than daily users and similar to weekly users',

  variants: {
    control: 'weekly_notifications',
    treatment: ['daily_notifications', '3x_week_notifications'],
  },

  // Primary metric: 7-day retention
  // Why: Retention is our north star metric. Users who keep coming back = engaged users.
  primaryMetrics: [
    {
      name: 'retention_7d',
      eventNames: ['app_open', 'content_viewed'],
      aggregationType: 'ratio',
      unitType: 'user',
      description: 'Percentage of users who had any activity in days 1-7 after first notification',
      direction: 'increase',
    },
  ],

  // Guardrail metrics: Ensure we don't cause negative side effects
  guardrailMetrics: [
    {
      name: 'notification_opt_out_rate',
      eventNames: ['notification_opt_out'],
      aggregationType: 'ratio',
      unitType: 'user',
      description: 'Percentage of users who disable notifications',
      direction: 'decrease',
      upperBound: 0.1, // Max 10% increase from control
      autoStopThreshold: 0.95, // 95% confidence needed to stop for guardrail breach
    },
    {
      name: 'complaint_rate',
      eventNames: ['notification_complained', 'feedback_negative'],
      aggregationType: 'ratio',
      unitType: 'user',
      description: 'Percentage of users filing complaints about notifications',
      direction: 'decrease',
      upperBound: 0.15,
    },
    {
      name: 'session_duration',
      eventNames: ['session_ended'],
      aggregationType: 'mean',
      unitType: 'session',
      description: 'Average session duration in minutes',
      direction: 'increase',
      lowerBound: -0.2, // Don't let sessions drop more than 20%
    },
  ],

  stats: {
    significanceLevel: 0.05, // 95% confidence
    power: 0.8, // 80% power (20% type II error)
    minSampleSize: 5000, // 5k per variant = 15k total
    samplingUnit: 'user',
    testType: 'two_tailed',
  },

  targetSegments: ['all_active_users'],
  rolloutPercentage: 10, // Start with 10% of active users

  progressiveRollout: {
    phase1Percentage: 10,
    phase1Duration: 7, // Run 1 week at 10%
    phase2Percentage: 50,
    phase2Duration: 7, // Then 50% for 1 week
    phase3Percentage: 100, // Then 100% if guardrails pass
  },

  startDate: new Date('2025-03-01'),
  endDate: new Date('2025-04-30'),

  monitoringInterval: 24, // Check daily
  checkGuardrails: true,
  autoStopOnGuardrailBreach: true,

  noveltyDetectionWindow: 14, // Check if effect persists after 2 weeks
  persistenceHoldout: 5, // Hold out 5% for 90-day retention tracking
  minRuntimeDays: 7,
};

/**
 * EXPERIMENT 2: Content Personalization V2
 *
 * Test: Collaborative filtering + content-based hybrid vs default ranking
 *
 * Hypothesis:
 * Users who see personalized recommendations based on collaborative filtering
 * will have:
 * - 15% longer average session duration
 * - Higher content completion rate
 * - Higher engagement score growth
 *
 * Rationale:
 * Current: Content ranked by popularity + recency only
 * Problem: Not personalized to individual preferences
 * Solution: Hybrid recommender combining "users like you also engaged" signals
 *          with content-based features
 */
export const CONTENT_PERSONALIZATION_EXPERIMENT: ExperimentInstance = {
  experimentId: 'content_personalization_v2',
  name: 'Content Personalization V2: Collaborative Filtering',
  description: 'Test hybrid collaborative filtering + content-based recommendation engine',
  hypothesis:
    'Users who see personalized content recommendations will have 15% longer session duration compared to default ranking',

  variants: {
    control: 'default_content_ranking',
    treatment: ['collaborative_filtering_hybrid'],
  },

  // Primary metric: Session duration
  // Why: Longer sessions = higher engagement, more opportunity for action
  primaryMetrics: [
    {
      name: 'session_duration',
      eventNames: ['session_ended'],
      aggregationType: 'mean',
      unitType: 'session',
      description: 'Average session duration in minutes',
      direction: 'increase',
    },
  ],

  // Guardrail metrics: Ensure recommendations are good quality
  guardrailMetrics: [
    {
      name: 'content_skip_rate',
      eventNames: ['content_skipped'],
      aggregationType: 'ratio',
      unitType: 'user',
      description: 'Percentage of recommendations skipped without viewing',
      direction: 'decrease',
      upperBound: 0.2, // Don't let skip rate increase > 20%
    },
    {
      name: 'feedback_negative_rate',
      eventNames: ['feedback_negative'],
      aggregationType: 'ratio',
      unitType: 'user',
      description: 'Percentage of recommendations marked as not helpful',
      direction: 'decrease',
      upperBound: 0.15,
    },
    {
      name: 'engagement_rate',
      eventNames: ['daily_active_engagement'],
      aggregationType: 'ratio',
      unitType: 'user',
      description: 'Percentage of users who engage each day',
      direction: 'increase',
    },
  ],

  secondaryMetrics: [
    {
      name: 'content_completion_rate',
      eventNames: ['content_completed'],
      aggregationType: 'ratio',
      unitType: 'user',
      description: 'Percentage of users who complete viewed content',
      direction: 'increase',
    },
    {
      name: 'engagement_score_growth',
      eventNames: ['engagement_score_updated'],
      aggregationType: 'mean',
      unitType: 'user',
      description: 'Average engagement score growth per user',
      direction: 'increase',
    },
  ],

  stats: {
    significanceLevel: 0.05,
    power: 0.8,
    minSampleSize: 10000, // 10k per variant = 20k total (larger due to noise in session data)
    samplingUnit: 'user',
    testType: 'two_tailed',
  },

  targetSegments: ['all_active_users'],
  rolloutPercentage: 20, // Start with 20% of active users

  progressiveRollout: {
    phase1Percentage: 20,
    phase1Duration: 7,
    phase2Percentage: 50,
    phase2Duration: 7,
    phase3Percentage: 100,
  },

  startDate: new Date('2025-03-15'),

  monitoringInterval: 24,
  checkGuardrails: true,
  autoStopOnGuardrailBreach: true,

  noveltyDetectionWindow: 14,
  persistenceHoldout: 5,
  minRuntimeDays: 10,
};

/**
 * EXPERIMENT 3: Streamlined Onboarding
 *
 * Test: Reduced onboarding flow (3 steps vs 5 steps)
 *
 * Hypothesis:
 * Users who complete streamlined 3-step onboarding will have:
 * - Higher activation rate (8% lift)
 * - Similar 7-day retention to 5-step flow
 * - Higher satisfaction with goal clarity
 *
 * Rationale:
 * Current: 5-step detailed onboarding
 * Problem: 35% drop-off rate during onboarding, users overwhelmed
 * Solution: Reduce to 3 core steps, collect other data through in-app experience
 */
export const ONBOARDING_OPTIMIZATION_EXPERIMENT: ExperimentInstance = {
  experimentId: 'onboarding_flow_optimization',
  name: 'Streamlined Onboarding Flow',
  description: 'Test simplified 3-step onboarding vs current 5-step flow',
  hypothesis:
    'Users who complete streamlined 3-step onboarding will have 8% higher activation rate than 5-step onboarding',

  variants: {
    control: 'full_onboarding_5_steps',
    treatment: ['streamlined_onboarding_3_steps'],
  },

  // Primary metric: Activation rate (first key action completion)
  primaryMetrics: [
    {
      name: 'activation_rate',
      eventNames: ['user_activated'],
      aggregationType: 'ratio',
      unitType: 'user',
      description: 'Percentage of signups who complete first key action',
      direction: 'increase',
    },
  ],

  // Guardrail metrics: Ensure we don't sacrifice quality for speed
  guardrailMetrics: [
    {
      name: 'onboarding_completion_rate',
      eventNames: ['onboarding_completed'],
      aggregationType: 'ratio',
      unitType: 'user',
      description: 'Percentage of users who finish onboarding',
      direction: 'increase',
    },
    {
      name: 'goal_clarity_score',
      eventNames: ['feedback_goal_clarity'],
      aggregationType: 'mean',
      unitType: 'user',
      description: 'Average user rating of goal clarity (1-5 scale)',
      direction: 'increase',
      lowerBound: -0.3, // Don't let clarity drop > 0.3 points on 5-point scale
    },
    {
      name: 'retention_7d',
      eventNames: ['app_open', 'content_viewed'],
      aggregationType: 'ratio',
      unitType: 'user',
      description: 'Percentage of new users retained at day 7',
      direction: 'increase',
    },
  ],

  stats: {
    significanceLevel: 0.05,
    power: 0.8,
    minSampleSize: 3000, // 3k per variant = 6k total (new users are high-traffic)
    samplingUnit: 'user',
    testType: 'two_tailed',
  },

  targetSegments: ['new_users'],
  rolloutPercentage: 50, // Can be more aggressive with new users

  progressiveRollout: {
    phase1Percentage: 50,
    phase1Duration: 7,
    phase2Percentage: 100,
    phase2Duration: 0, // If guardrails pass, go to 100%
    phase3Percentage: 100,
  },

  startDate: new Date('2025-03-08'),

  monitoringInterval: 24,
  checkGuardrails: true,
  autoStopOnGuardrailBreach: true,

  noveltyDetectionWindow: 14,
  persistenceHoldout: 5,
  minRuntimeDays: 7,
};

// ============================================================================
// EXPERIMENT TARGETING RULES
// ============================================================================

/**
 * Define which segments are eligible for each experiment
 */
export const EXPERIMENT_TARGETING: Record<string, TargetingRule[]> = {
  notification_frequency_test: [
    {
      type: 'segment',
      value: 'all_active_users',
      variantMap: {
        weekly_notifications: 33.33,
        daily_notifications: 33.33,
        '3x_week_notifications': 33.34,
      },
    },
  ],

  content_personalization_v2: [
    {
      type: 'segment',
      value: 'all_active_users',
      variantMap: {
        default_content_ranking: 50,
        collaborative_filtering_hybrid: 50,
      },
    },
  ],

  onboarding_flow_optimization: [
    {
      type: 'segment',
      value: 'new_users',
      variantMap: {
        full_onboarding_5_steps: 50,
        streamlined_onboarding_3_steps: 50,
      },
    },
  ],
};

// ============================================================================
// HELPER FUNCTIONS FOR EXPERIMENT MANAGEMENT
// ============================================================================

/**
 * Calculate required sample size using power analysis
 *
 * Uses continuous approximation of normal distribution
 * Formula: n = 2 * (Z_alpha/2 + Z_beta)^2 * σ^2 / δ^2
 */
export function calculateSampleSize(
  baselineConversionRate: number,
  minDetectableEffect: number,
  alpha: number = 0.05,
  beta: number = 0.2
): number {
  const Z_alpha = 1.96; // Two-tailed, α=0.05
  const Z_beta = 0.84; // β=0.2 (80% power)

  const p = baselineConversionRate;
  const variance = p * (1 - p);
  const delta = baselineConversionRate * minDetectableEffect;

  const n = (2 * Math.pow(Z_alpha + Z_beta, 2) * variance) / Math.pow(delta, 2);
  return Math.ceil(n);
}

/**
 * Calculate minimum detectable effect given sample size and baseline
 */
export function calculateMDE(
  sampleSize: number,
  baselineConversionRate: number,
  alpha: number = 0.05,
  beta: number = 0.2
): number {
  const Z_alpha = 1.96;
  const Z_beta = 0.84;

  const p = baselineConversionRate;
  const variance = p * (1 - p);

  const delta = ((Z_alpha + Z_beta) * Math.sqrt(2 * variance)) / Math.sqrt(sampleSize);
  return delta / baselineConversionRate;
}

/**
 * Get all experiments for a given status
 */
export function getExperimentsByStatus(status: string): ExperimentInstance[] {
  const allExperiments = [
    NOTIFICATION_FREQUENCY_EXPERIMENT,
    CONTENT_PERSONALIZATION_EXPERIMENT,
    ONBOARDING_OPTIMIZATION_EXPERIMENT,
  ];

  return allExperiments.filter((exp) => exp.startDate <= new Date() && (!exp.endDate || exp.endDate >= new Date()));
}

/**
 * Check if user is eligible for experiment based on targeting
 */
export function isUserEligibleForExperiment(
  userId: string,
  userSegments: string[],
  experimentId: string
): boolean {
  const targetingRules = EXPERIMENT_TARGETING[experimentId];
  if (!targetingRules) return false;

  return targetingRules.some((rule) => {
    if (rule.type === 'segment') {
      return userSegments.includes(rule.value as string);
    }
    if (rule.type === 'user_id') {
      return userId === rule.value;
    }
    return false;
  });
}

/**
 * Assign user to variant using deterministic hashing
 */
export function assignVariant(
  userId: string,
  experimentId: string,
  variants: string[],
  rolloutPercentage: number = 100
): string | null {
  // Simple deterministic assignment using hash
  // In production, use a proper hash function (e.g., murmur3)
  const combined = `${userId}:${experimentId}`;
  const hash = Array.from(combined).reduce((acc, char) => {
    return (acc << 5) - acc + char.charCodeAt(0);
  }, 0);

  const bucket = Math.abs(hash) % 100;

  // Check if user falls within rollout percentage
  if (bucket >= rolloutPercentage) {
    return null; // User not assigned (control)
  }

  // Assign to variant deterministically
  const variantIndex = Math.floor((bucket / rolloutPercentage) * variants.length) % variants.length;
  return variants[variantIndex];
}

export default {
  NOTIFICATION_FREQUENCY_EXPERIMENT,
  CONTENT_PERSONALIZATION_EXPERIMENT,
  ONBOARDING_OPTIMIZATION_EXPERIMENT,
  EXPERIMENT_TARGETING,
  calculateSampleSize,
  calculateMDE,
  getExperimentsByStatus,
  isUserEligibleForExperiment,
  assignVariant,
};
