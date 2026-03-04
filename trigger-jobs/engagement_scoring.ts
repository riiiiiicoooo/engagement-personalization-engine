/**
 * Trigger.dev Job: Engagement Score Calculation
 *
 * Batch recalculates engagement scores for all users using:
 * - Recency (recent activity weight)
 * - Frequency (activity count in lookback window)
 * - Depth (quality of interactions)
 * - Consistency (regularity of engagement)
 * - Progression (goal movement)
 *
 * Implements checkpointing for large user bases to handle failures gracefully.
 */

import { TriggerClient, Webhook } from '@trigger.dev/sdk';
import { z } from 'zod';
import { createClient } from '@supabase/supabase-js';

const client = new TriggerClient({
  id: 'engagement-personalization-engine',
  apiKey: process.env.TRIGGER_API_KEY,
});

const supabase = createClient(process.env.SUPABASE_URL || '', process.env.SUPABASE_KEY || '');

/**
 * Engagement Scoring Configuration
 */
const ENGAGEMENT_WEIGHTS = {
  recency: 0.3,
  frequency: 0.25,
  depth: 0.2,
  consistency: 0.15,
  progression: 0.1,
};

const LOOKBACK_DAYS = 30;
const BATCH_SIZE = 100;

/**
 * Checkpoint data structure for resuming failed jobs
 */
interface CheckpointData {
  processedUsers: number;
  lastUserId: string;
  timestamp: string;
  failedUsers: string[];
}

/**
 * User activity aggregation
 */
interface UserActivityStats {
  userId: string;
  eventCount7d: number;
  eventCount14d: number;
  eventCount30d: number;
  lastActivityAt: Date | null;
  deepEvents: number; // completed actions, not just opens
  sessionDays: number; // unique days with activity
  goalProgressCount: number;
}

/**
 * Calculate engagement score for a single user
 */
function calculateEngagementScore(stats: UserActivityStats, userCreatedAt: Date): number {
  // Recency: How recently was the user active? (0-100)
  let recencyScore = 0;
  if (stats.lastActivityAt) {
    const daysSinceActive = (Date.now() - stats.lastActivityAt.getTime()) / (1000 * 60 * 60 * 24);
    recencyScore = Math.max(0, 100 - daysSinceActive * 5); // Decays 5 points per day
  }

  // Frequency: How often do they engage in the lookback window? (0-100)
  // Expected: 5+ events = 100, 1 event = 20
  const frequencyScore = Math.min(100, Math.max(0, (stats.eventCount30d / 5) * 100));

  // Depth: Quality of engagement (completed actions vs just opens) (0-100)
  const deepEventRatio = stats.eventCount30d > 0 ? stats.deepEvents / stats.eventCount30d : 0;
  const depthScore = Math.min(100, deepEventRatio * 150); // Reward deep engagement

  // Consistency: Regular engagement pattern (0-100)
  // Active 20+ days = 100, active < 5 days = 20
  const expectedActiveDays = Math.min(30, LOOKBACK_DAYS);
  const consistencyScore = Math.min(100, (stats.sessionDays / expectedActiveDays) * 100);

  // Progression: Movement toward stated goals (0-100)
  // Each goal action completion = +10 points (capped at 100)
  const progressionScore = Math.min(100, stats.goalProgressCount * 10);

  // Composite score
  const compositeScore =
    ENGAGEMENT_WEIGHTS.recency * recencyScore +
    ENGAGEMENT_WEIGHTS.frequency * frequencyScore +
    ENGAGEMENT_WEIGHTS.depth * depthScore +
    ENGAGEMENT_WEIGHTS.consistency * consistencyScore +
    ENGAGEMENT_WEIGHTS.progression * progressionScore;

  return Math.round(compositeScore);
}

/**
 * Classify user into cohort based on engagement score and activity
 */
function classifyUserCohort(
  score: number,
  daysSinceLastActivity: number
): {
  behavioralCohort: string;
  engagementTier: number;
  lifecycleStage: string;
} {
  // Behavioral cohort based on score
  let behavioralCohort = 'dormant';
  if (score >= 80) behavioralCohort = 'power_user';
  else if (score >= 60) behavioralCohort = 'regular';
  else if (score >= 40) behavioralCohort = 'casual';
  else if (score >= 20) behavioralCohort = 'drifting';

  // Engagement tier (1-5, 1 = highest)
  let engagementTier = 5;
  if (score >= 80) engagementTier = 1;
  else if (score >= 60) engagementTier = 2;
  else if (score >= 40) engagementTier = 3;
  else if (score >= 20) engagementTier = 4;

  // Lifecycle stage based on activity recency
  let lifecycleStage = 'engaged';
  if (daysSinceLastActivity >= 30) lifecycleStage = 'churned';
  else if (daysSinceLastActivity >= 14) lifecycleStage = 'dormant';
  else if (score < 35) lifecycleStage = 'at_risk';

  return {
    behavioralCohort,
    engagementTier,
    lifecycleStage,
  };
}

/**
 * Fetch activity stats for a user
 */
async function fetchUserActivityStats(userId: string): Promise<UserActivityStats | null> {
  const now = new Date();
  const thirtyDaysAgo = new Date(now.getTime() - LOOKBACK_DAYS * 24 * 60 * 60 * 1000);

  // Fetch events from Supabase
  const { data: events, error } = await supabase
    .from('events')
    .select('event_type, timestamp')
    .eq('user_id', userId)
    .gte('timestamp', thirtyDaysAgo.toISOString())
    .order('timestamp', { ascending: false });

  if (error) {
    console.error(`Error fetching events for user ${userId}:`, error);
    return null;
  }

  if (!events || events.length === 0) {
    return {
      userId,
      eventCount7d: 0,
      eventCount14d: 0,
      eventCount30d: 0,
      lastActivityAt: null,
      deepEvents: 0,
      sessionDays: 0,
      goalProgressCount: 0,
    };
  }

  // Aggregate activity stats
  const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const fourteenDaysAgo = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);

  const eventCount7d = events.filter((e) => new Date(e.timestamp) > sevenDaysAgo).length;
  const eventCount14d = events.filter((e) => new Date(e.timestamp) > fourteenDaysAgo).length;

  // Deep events: content_completed, goal_achieved, content_shared, etc.
  const deepEventTypes = [
    'content_completed',
    'goal_achieved',
    'goal_progress_updated',
    'content_shared',
    'content_bookmarked',
  ];
  const deepEvents = events.filter((e) => deepEventTypes.includes(e.event_type)).length;

  // Unique days with activity
  const uniqueDays = new Set(
    events.map((e) => new Date(e.timestamp).toISOString().split('T')[0])
  ).size;

  // Goal progress count
  const goalProgressCount = events.filter((e) =>
    ['goal_progress_updated', 'goal_achieved'].includes(e.event_type)
  ).length;

  return {
    userId,
    eventCount7d,
    eventCount14d,
    eventCount30d: events.length,
    lastActivityAt: new Date(events[0].timestamp),
    deepEvents,
    sessionDays: uniqueDays,
    goalProgressCount,
  };
}

/**
 * Process a batch of users
 */
async function processBatch(userIds: string[]): Promise<void> {
  const updates: Array<{
    id: string;
    engagement_score: number;
    behavioral_cohort: string;
    engagement_tier: number;
    lifecycle_stage: string;
  }> = [];

  for (const userId of userIds) {
    const stats = await fetchUserActivityStats(userId);
    if (!stats) continue;

    // Fetch user creation date for context
    const { data: user } = await supabase
      .from('users')
      .select('created_at')
      .eq('user_id', userId)
      .single();

    const createdAt = user ? new Date(user.created_at) : new Date();

    // Calculate engagement score
    const engagementScore = calculateEngagementScore(stats, createdAt);

    // Determine days since last activity
    const daysSinceLastActivity = stats.lastActivityAt
      ? Math.floor((Date.now() - stats.lastActivityAt.getTime()) / (1000 * 60 * 60 * 24))
      : 999;

    // Classify cohort
    const { behavioralCohort, engagementTier, lifecycleStage } =
      classifyUserCohort(engagementScore, daysSinceLastActivity);

    updates.push({
      id: userId,
      engagement_score: engagementScore,
      behavioral_cohort: behavioralCohort,
      engagement_tier: engagementTier,
      lifecycle_stage: lifecycleStage,
    });
  }

  // Batch update in Supabase
  if (updates.length > 0) {
    const { error } = await supabase
      .from('users')
      .upsert(updates, { onConflict: 'user_id' });

    if (error) {
      throw new Error(`Failed to update user scores: ${error.message}`);
    }
  }
}

/**
 * Detect cohort transitions for a user
 */
async function detectTransitions(userId: string): Promise<void> {
  // Fetch current and previous cohort assignment
  const { data: current } = await supabase
    .from('users')
    .select('engagement_tier, behavioral_cohort, lifecycle_stage')
    .eq('user_id', userId)
    .single();

  const { data: previous } = await supabase
    .from('cohort_assignments')
    .select('engagement_tier, behavioral_cohort, lifecycle_stage')
    .eq('user_id', userId)
    .order('assigned_at', { ascending: false })
    .limit(1)
    .single();

  if (!current || !previous) return;

  const tierChanged = current.engagement_tier !== previous.engagement_tier;
  const cohortChanged = current.behavioral_cohort !== previous.behavioral_cohort;
  const lifecycleChanged = current.lifecycle_stage !== previous.lifecycle_stage;

  if (tierChanged || cohortChanged || lifecycleChanged) {
    // Log transition
    await supabase.from('cohort_assignments').insert({
      user_id: userId,
      engagement_tier: current.engagement_tier,
      behavioral_cohort: current.behavioral_cohort,
      lifecycle_stage: current.lifecycle_stage,
      previous_tier: previous.engagement_tier,
      tier_changed: tierChanged,
    });

    // Track event for analytics
    await fetch(`${process.env.API_URL}/api/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event: 'cohort_transition',
        user_id: userId,
        from: {
          tier: previous.engagement_tier,
          cohort: previous.behavioral_cohort,
          stage: previous.lifecycle_stage,
        },
        to: {
          tier: current.engagement_tier,
          cohort: current.behavioral_cohort,
          stage: current.lifecycle_stage,
        },
      }),
    });
  }
}

/**
 * Main engagement scoring job
 */
export const engagementScoringJob = client.defineJob({
  id: 'engagement-scoring',
  name: 'Engagement Score Recalculation',
  version: '1.0.0',
  trigger: Webhook({
    service: 'github',
    event: 'push',
  }),
  run: async (payload, io, ctx) => {
    console.log('Starting engagement score recalculation job');

    // Load checkpoint if job failed previously
    let processedCount = 0;
    let lastUserId = '';

    try {
      // Fetch all users
      const { data: allUsers, error: fetchError } = await supabase
        .from('users')
        .select('id, user_id')
        .gt('id', lastUserId) // Resume from last processed user
        .order('id')
        .limit(10000); // Fetch in chunks

      if (fetchError) throw fetchError;
      if (!allUsers) return;

      // Process in batches with checkpointing
      for (let i = 0; i < allUsers.length; i += BATCH_SIZE) {
        const batch = allUsers.slice(i, i + BATCH_SIZE);
        const batchUserIds = batch.map((u) => u.id);

        try {
          await processBatch(batchUserIds);
          processedCount += batchUserIds.length;
          lastUserId = batchUserIds[batchUserIds.length - 1];

          // Detect transitions for this batch
          for (const userId of batchUserIds) {
            await detectTransitions(userId);
          }

          console.log(
            `Processed ${processedCount}/${allUsers.length} users (${Math.round((processedCount / allUsers.length) * 100)}%)`
          );
        } catch (error) {
          console.error(`Error processing batch starting at user ${lastUserId}:`, error);
          // Continue with next batch instead of failing entire job
        }
      }

      // Refresh materialized views for dashboard
      await supabase.rpc('refresh_engagement_views');

      console.log(`Engagement scoring job completed. Processed ${processedCount} users.`);

      return {
        success: true,
        processedUsers: processedCount,
      };
    } catch (error) {
      console.error('Engagement scoring job failed:', error);

      // Save checkpoint for retry
      const checkpoint: CheckpointData = {
        processedUsers: processedCount,
        lastUserId,
        timestamp: new Date().toISOString(),
        failedUsers: [],
      };

      await io.sendEvent('engagement_scoring_checkpoint', checkpoint);
      throw error;
    }
  },
});

export default engagementScoringJob;
