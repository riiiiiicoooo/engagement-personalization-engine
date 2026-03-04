/**
 * Trigger.dev Job: Personalized Content Recommendation Generation
 *
 * Generates personalized content recommendations for each user using:
 * - Collaborative filtering: "Users like you engaged with X"
 * - Content-based filtering: "Based on your history, you'll like X"
 * - Thompson sampling for exploration/exploitation
 *
 * Recommendations are generated nightly and populated into the recommendations table
 * for retrieval by the API.
 */

import { TriggerClient, Webhook } from '@trigger.dev/sdk';
import { createClient } from '@supabase/supabase-js';

const client = new TriggerClient({
  id: 'engagement-personalization-engine',
  apiKey: process.env.TRIGGER_API_KEY,
});

const supabase = createClient(process.env.SUPABASE_URL || '', process.env.SUPABASE_KEY || '');

/**
 * Recommendation Configuration
 */
const CONFIG = {
  RECOMMENDATIONS_PER_USER: 10,
  DEDUP_WINDOW_HOURS: 48,
  CONTENT_POOL_SIZE: 1000,
  BATCH_SIZE: 50,
  MIN_ENGAGEMENT_THRESHOLD: 0.3, // Min 30% engagement to use user's data in CF
};

/**
 * Recommendation scoring components
 */
interface RecommendationScore {
  contentId: string;
  title: string;
  contentType: string;
  collaborativeScore: number;
  contentAffinity: number;
  freshnessBoost: number;
  diversityPenalty: number;
  tierAdjustment: number;
  finalScore: number;
  reason: string;
}

/**
 * User profile for recommendation engine
 */
interface UserProfile {
  userId: string;
  engagementTier: number;
  behavioralCohort: string;
  goalCluster: string;
  recentContentIds: string[];
  interactionHistory: Map<string, number>; // contentId -> engagement score
  lastRecs: string[]; // Recently recommended to avoid duplication
}

/**
 * Fetch user profile for recommendations
 */
async function fetchUserProfile(userId: string): Promise<UserProfile | null> {
  // Fetch user info
  const { data: user } = await supabase
    .from('users')
    .select('user_id, engagement_tier, behavioral_cohort, goal_cluster')
    .eq('id', userId)
    .single();

  if (!user) return null;

  // Fetch recent interactions (last 7 days)
  const { data: interactions } = await supabase
    .from('recommendations')
    .select('content_id, score')
    .eq('user_id', userId)
    .gte('created_at', new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString())
    .limit(100);

  // Fetch recently recommended content (to avoid duplication)
  const { data: recentRecs } = await supabase
    .from('recommendations')
    .select('content_id')
    .eq('user_id', userId)
    .gte('created_at', new Date(Date.now() - CONFIG.DEDUP_WINDOW_HOURS * 60 * 60 * 1000).toISOString());

  const interactionHistory = new Map<string, number>();
  if (interactions) {
    interactions.forEach((i) => {
      interactionHistory.set(i.content_id, i.score || 0.5);
    });
  }

  const lastRecs = recentRecs ? recentRecs.map((r) => r.content_id) : [];

  return {
    userId,
    engagementTier: user.engagement_tier,
    behavioralCohort: user.behavioral_cohort,
    goalCluster: user.goal_cluster,
    recentContentIds: Array.from(interactionHistory.keys()),
    interactionHistory,
    lastRecs,
  };
}

/**
 * Thompson Sampling for exploration/exploitation
 *
 * Sample from Beta distribution to balance:
 * - Exploitation: Recommend content we know user will like
 * - Exploration: Try new content to learn preferences
 */
function thompsonSampleScore(successCount: number, failureCount: number): number {
  // Simple beta-binomial approximation
  // Real implementation would use proper Beta distribution sampling
  const alpha = successCount + 1;
  const beta = failureCount + 1;
  const mean = alpha / (alpha + beta);
  const variance = (alpha * beta) / (Math.pow(alpha + beta, 2) * (alpha + beta + 1));

  // Add exploration bonus via variance
  return mean + Math.sqrt(variance);
}

/**
 * Calculate collaborative filtering score
 *
 * Find users similar to target user and score content they engaged with
 */
async function calculateCollaborativeScore(
  userId: string,
  userProfile: UserProfile,
  contentId: string
): Promise<number> {
  // Find similar users (same tier, cohort, or goal cluster)
  const { data: similarUsers } = await supabase
    .from('users')
    .select('id')
    .eq('engagement_tier', userProfile.engagementTier)
    .neq('id', userId)
    .limit(500);

  if (!similarUsers || similarUsers.length === 0) return 0;

  // Count how many similar users engaged with this content
  const { data: engagements } = await supabase
    .from('recommendations')
    .select('user_id, score')
    .eq('content_id', contentId)
    .in(
      'user_id',
      similarUsers.map((u) => u.id)
    )
    .gte('score', 0.6); // Only count positive engagements

  if (!engagements || engagements.length === 0) return 0;

  // Score based on how many similar users liked it
  const engagementRatio = engagements.length / similarUsers.length;
  const avgEngagementScore = engagements.reduce((sum, e) => sum + (e.score || 0), 0) / engagements.length;

  // Thompson sample based on observed engagement
  return thompsonSampleScore(engagements.length, similarUsers.length - engagements.length) * avgEngagementScore;
}

/**
 * Calculate content-based affinity score
 *
 * Compare content features to user's interaction history
 */
async function calculateContentAffinity(
  userProfile: UserProfile,
  contentId: string
): Promise<number> {
  // Fetch content metadata
  const { data: content } = await supabase
    .from('content_metadata') // Hypothetical table
    .select('id, category, difficulty, duration, topic_tags')
    .eq('id', contentId)
    .single();

  if (!content) return 0;

  // Calculate similarity to content user previously engaged with
  let totalSimilarity = 0;
  let similarityCount = 0;

  for (const [prevContentId, engagementScore] of userProfile.interactionHistory.entries()) {
    if (engagementScore < 0.3) continue; // Only consider positive engagements

    const { data: prevContent } = await supabase
      .from('content_metadata')
      .select('category, topic_tags')
      .eq('id', prevContentId)
      .single();

    if (!prevContent) continue;

    // Simple similarity: same category + overlapping tags
    let similarity = 0;
    if (content.category === prevContent.category) similarity += 0.5;

    if (content.topic_tags && prevContent.topic_tags) {
      const overlap = content.topic_tags.filter((tag: string) => prevContent.topic_tags.includes(tag)).length;
      const union = new Set([...content.topic_tags, ...prevContent.topic_tags]).size;
      similarity += (overlap / union) * 0.5;
    }

    totalSimilarity += similarity * engagementScore;
    similarityCount += 1;
  }

  return similarityCount > 0 ? totalSimilarity / similarityCount : 0;
}

/**
 * Calculate freshness boost
 *
 * New content gets temporary lift to explore
 */
function calculateFreshnessBoost(contentPublishedAt: Date): number {
  const daysOld = (Date.now() - contentPublishedAt.getTime()) / (1000 * 60 * 60 * 24);

  if (daysOld <= 1) return 0.3; // Brand new
  if (daysOld <= 7) return 0.15; // Recent
  if (daysOld <= 30) return 0.05; // Fairly new
  return 0; // Old content
}

/**
 * Calculate diversity penalty
 *
 * Penalize recommending multiple articles on same topic
 */
function calculateDiversityPenalty(
  contentId: string,
  topicTag: string,
  rankedSoFar: RecommendationScore[]
): number {
  const sameTopicCount = rankedSoFar.filter((r) => r.contentType === topicTag).length;

  if (sameTopicCount === 0) return 0;
  if (sameTopicCount === 1) return 0.15;
  if (sameTopicCount === 2) return 0.35;
  return 0.5; // Heavily penalize if we already have 3+ on this topic
}

/**
 * Apply tier-based adjustment
 *
 * Users in tier 4-5 (low engagement) get simpler, lower-barrier content
 */
function calculateTierAdjustment(engagementTier: number, contentDifficulty: number): number {
  // contentDifficulty: 1=easy, 2=medium, 3=hard

  if (engagementTier <= 2) {
    // High engagement users: no penalty
    return 0;
  } else if (engagementTier === 3) {
    // Medium engagement: slight penalty for hard content
    return contentDifficulty === 3 ? -0.1 : 0;
  } else {
    // Low engagement (tier 4-5): penalize medium/hard content
    return contentDifficulty === 1 ? 0.1 : contentDifficulty === 2 ? -0.15 : -0.3;
  }
}

/**
 * Score and rank content for a user
 */
async function scoreAndRankContent(
  userId: string,
  userProfile: UserProfile,
  contentPool: Array<{ id: string; title: string; type: string; difficulty: number; publishedAt: Date; topic: string }>
): Promise<RecommendationScore[]> {
  const rankedContent: RecommendationScore[] = [];

  for (const content of contentPool) {
    // Skip if recently recommended
    if (userProfile.lastRecs.includes(content.id)) continue;

    // Calculate scoring components
    const collaborativeScore = await calculateCollaborativeScore(userId, userProfile, content.id);
    const contentAffinity = await calculateContentAffinity(userProfile, content.id);
    const freshnessBoost = calculateFreshnessBoost(content.publishedAt);
    const diversityPenalty = calculateDiversityPenalty(content.id, content.topic, rankedContent);
    const tierAdjustment = calculateTierAdjustment(userProfile.engagementTier, content.difficulty);

    // Composite score
    const finalScore =
      0.4 * collaborativeScore + // Collaborative filtering weight
      0.35 * contentAffinity + // Content-based weight
      0.15 * freshnessBoost + // Freshness weight
      tierAdjustment - // Tier adjustment (can be negative)
      diversityPenalty; // Diversity penalty

    // Determine recommendation reason
    let reason = 'other';
    if (collaborativeScore > contentAffinity) {
      reason = 'collaborative_filtering';
    } else if (contentAffinity > collaborativeScore) {
      reason = 'content_affinity';
    } else if (freshnessBoost > 0.1) {
      reason = 'trending';
    }

    rankedContent.push({
      contentId: content.id,
      title: content.title,
      contentType: content.type,
      collaborativeScore,
      contentAffinity,
      freshnessBoost,
      diversityPenalty,
      tierAdjustment,
      finalScore,
      reason,
    });
  }

  // Sort by final score
  return rankedContent.sort((a, b) => b.finalScore - a.finalScore);
}

/**
 * Generate recommendations for a single user
 */
async function generateUserRecommendations(userId: string): Promise<void> {
  // Fetch user profile
  const userProfile = await fetchUserProfile(userId);
  if (!userProfile) return;

  // Fetch content pool
  const { data: contentPool } = await supabase
    .from('content')
    .select('id, title, type, difficulty, published_at, topic')
    .eq('status', 'published')
    .order('published_at', { ascending: false })
    .limit(CONFIG.CONTENT_POOL_SIZE);

  if (!contentPool || contentPool.length === 0) return;

  // Score and rank content
  const rankedContent = await scoreAndRankContent(userId, userProfile, contentPool);

  // Save top N recommendations
  const recommendations = rankedContent.slice(0, CONFIG.RECOMMENDATIONS_PER_USER).map((rec, index) => ({
    user_id: userId,
    content_id: rec.contentId,
    content_type: rec.contentType,
    content_title: rec.title,
    rank: index + 1,
    score: rec.finalScore,
    reason: rec.reason,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // Refresh daily
  }));

  // Delete old recommendations for this user
  await supabase.from('recommendations').delete().eq('user_id', userId).lt('expires_at', new Date().toISOString());

  // Insert new recommendations
  if (recommendations.length > 0) {
    await supabase.from('recommendations').insert(recommendations);
  }
}

/**
 * Main recommendation generation job
 */
export const recommendationGenerationJob = client.defineJob({
  id: 'recommendation-generation',
  name: 'Nightly Recommendation Generation',
  version: '1.0.0',
  trigger: Webhook({
    service: 'github',
    event: 'push',
  }),
  run: async (payload, io, ctx) => {
    console.log('Starting recommendation generation job');

    try {
      // Fetch all active users
      const { data: users, error: fetchError } = await supabase
        .from('users')
        .select('id')
        .neq('engagement_tier', 5) // Skip churned users
        .order('updated_at', { ascending: false });

      if (fetchError) throw fetchError;
      if (!users) return;

      let processed = 0;
      const errors: string[] = [];

      // Process in batches
      for (let i = 0; i < users.length; i += CONFIG.BATCH_SIZE) {
        const batch = users.slice(i, i + CONFIG.BATCH_SIZE);

        const results = await Promise.allSettled(
          batch.map((user) => generateUserRecommendations(user.id))
        );

        results.forEach((result, index) => {
          if (result.status === 'fulfilled') {
            processed++;
          } else {
            errors.push(`User ${batch[index].id}: ${result.reason}`);
          }
        });

        console.log(`Generated recommendations for ${processed}/${users.length} users`);
      }

      console.log(`Recommendation generation completed. Processed ${processed} users with ${errors.length} errors.`);

      return {
        success: true,
        processedUsers: processed,
        errors: errors.slice(0, 10), // Return first 10 errors
      };
    } catch (error) {
      console.error('Recommendation generation job failed:', error);
      throw error;
    }
  },
});

export default recommendationGenerationJob;
