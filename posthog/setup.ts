/**
 * PostHog Integration Setup
 *
 * Initializes PostHog with:
 * - Feature flag definitions
 * - Experiment configurations
 * - Custom event tracking
 * - Group analytics for cohort analysis
 */

import { PostHog } from 'posthog-node';

export interface PostHogConfig {
  apiKey: string;
  apiHost: string;
  flushInterval?: number;
}

/**
 * Initialize PostHog client for server-side usage
 */
export function initializePostHog(config: PostHogConfig): PostHog {
  const client = new PostHog(config.apiKey, {
    host: config.apiHost,
    flushInterval: config.flushInterval || 30000,
    featureFlagsPollingInterval: 300000, // Poll flags every 5 minutes
  });

  return client;
}

/**
 * Feature Flag Definitions
 *
 * These flags control major product features and experimentation variants
 */
export const FEATURE_FLAGS = {
  // Notification system flags
  NOTIFICATION_SYSTEM_V2: 'notification_system_v2',
  NOTIFICATION_FREQUENCY_WEEKLY: 'notification_frequency_weekly',
  NOTIFICATION_FREQUENCY_DAILY: 'notification_frequency_daily',
  OPTIMAL_SEND_TIME: 'optimal_send_time',

  // Content personalization flags
  PERSONALIZED_FEED: 'personalized_feed',
  COLLABORATIVE_FILTERING: 'collaborative_filtering',
  CONTENT_DIVERSITY_RANKING: 'content_diversity_ranking',

  // Onboarding and user experience
  STREAMLINED_ONBOARDING: 'streamlined_onboarding',
  SMART_GOAL_CLUSTERING: 'smart_goal_clustering',
  ENGAGEMENT_NUDGES: 'engagement_nudges',

  // Analytics and internal
  POSTHOG_ANALYTICS: 'posthog_analytics',
  DETAILED_EVENT_LOGGING: 'detailed_event_logging',
} as const;

/**
 * Experiment Definitions
 *
 * Define all active experiments with:
 * - Primary metrics
 * - Guardrail metrics
 * - Statistical configuration
 * - Variants
 */
export interface ExperimentConfig {
  id: string;
  name: string;
  description: string;
  hypothesis: string;
  status: 'draft' | 'running' | 'paused' | 'completed';
  variants: {
    control: string;
    treatments: string[];
  };
  primaryMetric: string;
  guardrailMetrics: string[];
  minSampleSize: number;
  significanceLevel: number; // 0.05 for 95% confidence
  mde: number; // Minimum detectable effect as percentage
  targetSegment?: string;
  targetPercentage: number; // 0-100
  startDate?: Date;
  endDate?: Date;
}

export const EXPERIMENTS: Record<string, ExperimentConfig> = {
  notification_frequency_test: {
    id: 'notification_frequency_test',
    name: 'Notification Frequency Optimization',
    description: 'Test different notification frequencies to maximize engagement without increasing opt-out',
    hypothesis:
      'Users who receive notifications 3x per week will have higher 7-day retention than daily or weekly groups',
    status: 'running',
    variants: {
      control: 'weekly_notifications',
      treatments: ['daily_notifications', '3x_week_notifications'],
    },
    primaryMetric: 'retention_7d',
    guardrailMetrics: ['notification_opt_out_rate', 'complaint_rate', 'session_duration'],
    minSampleSize: 5000,
    significanceLevel: 0.05,
    mde: 0.03, // 3% minimum detectable effect
    targetSegment: 'all_active_users',
    targetPercentage: 30,
  },

  content_personalization_v2: {
    id: 'content_personalization_v2',
    name: 'Content Personalization V2',
    description: 'Test new collaborative filtering + content-based hybrid recommendation engine',
    hypothesis:
      'Users who see personalized content recommendations based on collaborative filtering will engage 15% longer per session',
    status: 'running',
    variants: {
      control: 'default_content_ranking',
      treatments: ['collaborative_filtering_hybrid', 'collaborative_filtering_only'],
    },
    primaryMetric: 'session_duration',
    guardrailMetrics: ['content_skip_rate', 'feedback_negative_rate', 'daily_active_engagement_rate'],
    minSampleSize: 10000,
    significanceLevel: 0.05,
    mde: 0.05, // 5% minimum detectable effect on session duration
    targetSegment: 'all_active_users',
    targetPercentage: 40,
  },

  onboarding_flow_optimization: {
    id: 'onboarding_flow_optimization',
    name: 'Streamlined Onboarding Flow',
    description: 'Test simplified onboarding with fewer required steps to reduce drop-off',
    hypothesis:
      'Users who complete the streamlined 3-step onboarding will have higher activation rate (first key action) compared to 5-step flow',
    status: 'running',
    variants: {
      control: 'full_onboarding_5_steps',
      treatments: ['streamlined_onboarding_3_steps'],
    },
    primaryMetric: 'activation_rate',
    guardrailMetrics: ['onboarding_completion_rate', 'goal_clarity_score', '7day_retention'],
    minSampleSize: 3000,
    significanceLevel: 0.05,
    mde: 0.08, // 8% minimum detectable effect on activation
    targetSegment: 'new_users',
    targetPercentage: 50,
  },
};

/**
 * Custom Event Definitions
 *
 * Standardized event taxonomy for engagement tracking
 */
export const CUSTOM_EVENTS = {
  // User lifecycle events
  USER_SIGNUP: 'user_signup',
  USER_ACTIVATED: 'user_activated', // Completed first key action
  USER_REACTIVATED: 'user_reactivated',
  USER_CHURNED: 'user_churned',

  // Content interaction events
  CONTENT_VIEWED: 'content_viewed',
  CONTENT_STARTED: 'content_started',
  CONTENT_COMPLETED: 'content_completed',
  CONTENT_SHARED: 'content_shared',
  CONTENT_BOOKMARKED: 'content_bookmarked',

  // Engagement events
  SESSION_STARTED: 'session_started',
  SESSION_ENDED: 'session_ended',
  GOAL_PROGRESS_UPDATED: 'goal_progress_updated',
  GOAL_ACHIEVED: 'goal_achieved',

  // Notification events
  NOTIFICATION_SENT: 'notification_sent',
  NOTIFICATION_OPENED: 'notification_opened',
  NOTIFICATION_CLICKED: 'notification_clicked',
  NOTIFICATION_OPT_OUT: 'notification_opt_out',
  NOTIFICATION_COMPLAINED: 'notification_complained',

  // Feature flag events
  FEATURE_FLAG_EVALUATED: 'feature_flag_evaluated',

  // Experimentation events
  EXPERIMENT_EXPOSED: 'experiment_exposed',
  EXPERIMENT_METRIC_RECORDED: 'experiment_metric_recorded',

  // Recommendation events
  RECOMMENDATION_VIEWED: 'recommendation_viewed',
  RECOMMENDATION_CLICKED: 'recommendation_clicked',
  RECOMMENDATION_SKIPPED: 'recommendation_skipped',

  // Engagement score events
  ENGAGEMENT_SCORE_UPDATED: 'engagement_score_updated',
  COHORT_CHANGED: 'cohort_changed',
} as const;

/**
 * Group Analytics Setup
 *
 * Configure group tracking for cohort analysis
 */
export interface GroupAnalyticsConfig {
  propertyName: string;
  description: string;
}

export const GROUP_TYPES: Record<string, GroupAnalyticsConfig> = {
  cohort: {
    propertyName: 'cohort_name',
    description: 'User behavioral cohort (power_user, regular, casual, drifting, dormant)',
  },
  engagement_tier: {
    propertyName: 'engagement_tier',
    description: 'Engagement tier (1-5) for segmentation',
  },
  goal_cluster: {
    propertyName: 'goal_cluster',
    description: 'User goal cluster (weight_mgmt, fitness, mental_wellness, etc)',
  },
  lifecycle_stage: {
    propertyName: 'lifecycle_stage',
    description: 'User lifecycle stage (new, activated, engaged, at-risk, dormant, reactivated)',
  },
};

/**
 * Track a custom event with PostHog
 */
export function trackEvent(
  client: PostHog,
  userId: string,
  event: string,
  properties: Record<string, any> = {}
): void {
  client.capture({
    distinctId: userId,
    event,
    properties,
    timestamp: new Date(),
  });
}

/**
 * Track an experiment exposure
 */
export function trackExperimentExposure(
  client: PostHog,
  userId: string,
  experimentId: string,
  variant: string,
  properties: Record<string, any> = {}
): void {
  trackEvent(client, userId, CUSTOM_EVENTS.EXPERIMENT_EXPOSED, {
    experimentId,
    variant,
    ...properties,
  });
}

/**
 * Track feature flag evaluation
 */
export function trackFeatureFlagEvaluation(
  client: PostHog,
  userId: string,
  flagKey: string,
  flagValue: boolean,
  properties: Record<string, any> = {}
): void {
  trackEvent(client, userId, CUSTOM_EVENTS.FEATURE_FLAG_EVALUATED, {
    flagKey,
    flagValue,
    ...properties,
  });
}

/**
 * Set user properties for segmentation
 */
export function setUserProperties(
  client: PostHog,
  userId: string,
  properties: Record<string, any>
): void {
  client.identify({
    distinctId: userId,
    properties,
  });
}

/**
 * Set group properties for cohort analysis
 */
export function setGroupProperties(
  client: PostHog,
  groupKey: string,
  groupId: string,
  properties: Record<string, any>
): void {
  client.groupIdentify({
    groupKey,
    groupId,
    properties,
  });
}

/**
 * Associate user with a group
 */
export function associateUserWithGroup(
  client: PostHog,
  userId: string,
  groupKey: string,
  groupId: string
): void {
  client.capture({
    distinctId: userId,
    event: '$groupidentify',
    properties: {
      $group_key: groupKey,
      $group_id: groupId,
    },
  });
}

/**
 * Evaluate feature flag for user
 */
export async function evaluateFeatureFlag(
  client: PostHog,
  userId: string,
  flagKey: string
): Promise<boolean> {
  try {
    const isFeatureEnabled = await client.isFeatureEnabled(flagKey, userId);
    return isFeatureEnabled || false;
  } catch (error) {
    console.error(`Error evaluating feature flag ${flagKey}:`, error);
    return false;
  }
}

/**
 * Get all feature flags for a user
 */
export async function getFeatureFlags(
  client: PostHog,
  userId: string
): Promise<Record<string, boolean>> {
  try {
    const flags = await client.getAllFlags(userId);
    return flags || {};
  } catch (error) {
    console.error('Error fetching feature flags:', error);
    return {};
  }
}

/**
 * Export default configuration for use in applications
 */
export const posthogConfig = {
  apiKey: process.env.POSTHOG_API_KEY || '',
  apiHost: process.env.POSTHOG_API_HOST || 'https://app.posthog.com',
};

export default {
  initializePostHog,
  FEATURE_FLAGS,
  EXPERIMENTS,
  CUSTOM_EVENTS,
  GROUP_TYPES,
  trackEvent,
  trackExperimentExposure,
  trackFeatureFlagEvaluation,
  setUserProperties,
  setGroupProperties,
  associateUserWithGroup,
  evaluateFeatureFlag,
  getFeatureFlags,
};
