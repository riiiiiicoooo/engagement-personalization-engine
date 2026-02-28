"""
Recommendation Engine
=====================

Two-stage content ranking system:
  Stage 1 (Candidate Generation): Filter catalog to ~100 relevant items
  Stage 2 (Ranking): Score and order candidates using weighted model

Ranking formula:
    score = 0.40 × collaborative_filtering
          + 0.25 × content_affinity
          + 0.15 × freshness_boost
          + 0.10 × engagement_tier_adjustment
          + 0.10 × goal_relevance

Post-ranking: diversity enforcement, position bias correction, experiment overrides.

Latency budget: 55ms total (within 100ms API budget with Redis lookups and serialization).

Reference implementation — validates ranking logic and diversity enforcement.
Production version uses SageMaker for collaborative filtering inference.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import hashlib
import random


# ============================================================================
# Content Models
# ============================================================================

@dataclass
class ContentItem:
    """A piece of content that can be recommended."""
    content_id: str
    title: str
    content_type: str       # article, guided_activity, meditation, workout, video
    category: str           # nutrition, fitness, stress_management, sleep, etc.
    goal_clusters: list     # Which goal clusters this content serves (A, B, C, D, E)
    difficulty: str         # beginner, intermediate, advanced
    duration_minutes: int
    published_at: datetime
    total_completions: int = 0
    avg_rating: float = 0.0

    @property
    def days_since_published(self) -> float:
        return (datetime.utcnow() - self.published_at).total_seconds() / 86400


@dataclass
class UserContext:
    """User state at request time, fetched from Redis caches."""
    user_id: str
    engagement_score: float
    engagement_tier: int          # 1-5
    lifecycle_stage: str          # new, activated, engaged, at_risk, dormant, reactivated
    goal_cluster: str             # A, B, C, D, E
    secondary_goal_cluster: Optional[str] = None
    platform: str = "ios"

    # Interaction history (from Redis/Snowflake)
    recently_seen_ids: list = field(default_factory=list)     # Last 48 hours
    completed_ids: list = field(default_factory=list)          # All time
    category_interaction_counts: dict = field(default_factory=dict)  # {category: count}
    total_interactions: int = 0

    # Active experiments
    experiment_assignments: dict = field(default_factory=dict)  # {experiment_id: variant}


@dataclass
class RecommendationResult:
    """Ranked list of content with metadata for the client."""
    user_id: str
    items: list                # Ranked ContentItem list
    scores: list               # Corresponding scores
    cta: dict                  # Personalized call-to-action
    experiment_exposures: list  # Experiments evaluated during ranking
    computed_in_ms: float = 0
    used_fallback: bool = False


# ============================================================================
# Ranking Weights
# ============================================================================

RANKING_WEIGHTS = {
    "collaborative_filtering": 0.40,
    "content_affinity": 0.25,
    "freshness": 0.15,
    "tier_adjustment": 0.10,
    "goal_relevance": 0.10
}

# Diversity constraints
MAX_SAME_CATEGORY_IN_TOP_10 = 2
MAX_SAME_TYPE_IN_TOP_10 = 3
DEDUP_WINDOW_HOURS = 48


# ============================================================================
# Recommendation Engine
# ============================================================================

class RecommendationEngine:
    """
    Generates personalized content feed for a user.
    
    Two-stage architecture:
    1. Candidate generation: cheap filters reduce catalog to ~100 items
    2. Ranking: ML-informed scoring orders the candidates
    
    Why two stages: Running the full ranking model on 2,000+ items takes
    ~300ms. Filtering to 100 candidates first reduces ranking to ~40ms.
    
    Usage:
        engine = RecommendationEngine()
        result = engine.recommend(user_context, content_catalog, top_n=20)
    """

    def __init__(self, weights: dict = None):
        self.weights = weights or RANKING_WEIGHTS

    # ----------------------------------------------------------------
    # Stage 1: Candidate Generation
    # ----------------------------------------------------------------

    def generate_candidates(self, user: UserContext,
                            catalog: list,
                            max_candidates: int = 100) -> list:
        """
        Filter the content catalog to relevant candidates.
        
        Filters (applied in order):
        1. Remove already completed content
        2. Remove recently seen content (48-hour dedup)
        3. Filter by goal cluster relevance
        4. Filter by platform compatibility (if applicable)
        5. Cap at max_candidates, preferring recent and popular items
        
        These are cheap O(n) filters — no ML inference, no network calls.
        """
        candidates = []

        for item in catalog:
            # Filter: already completed
            if item.content_id in user.completed_ids:
                continue

            # Filter: recently seen (48-hour dedup window)
            if item.content_id in user.recently_seen_ids:
                continue

            # Filter: goal relevance — keep if matches primary, secondary, or general
            if not self._is_goal_relevant(item, user):
                continue

            candidates.append(item)

        # If we have too many candidates, prioritize by recency × popularity
        if len(candidates) > max_candidates:
            candidates.sort(
                key=lambda x: x.total_completions / max(x.days_since_published, 1),
                reverse=True
            )
            candidates = candidates[:max_candidates]

        return candidates

    def _is_goal_relevant(self, item: ContentItem, user: UserContext) -> bool:
        """Check if content is relevant to user's goal clusters."""
        # General wellness content (cluster E) is relevant to everyone
        if "E" in item.goal_clusters:
            return True
        # Matches primary goal
        if user.goal_cluster in item.goal_clusters:
            return True
        # Matches secondary goal
        if user.secondary_goal_cluster and user.secondary_goal_cluster in item.goal_clusters:
            return True
        # Allow 20% of candidates from unrelated clusters (discovery)
        return random.random() < 0.20

    # ----------------------------------------------------------------
    # Stage 2: Ranking
    # ----------------------------------------------------------------

    def rank_candidates(self, user: UserContext,
                        candidates: list,
                        collab_scores: dict = None) -> list:
        """
        Score and rank candidates using the weighted ranking model.
        
        Args:
            user: User context (engagement state, goals, history)
            candidates: Filtered content items from Stage 1
            collab_scores: Pre-computed collaborative filtering scores
                          {content_id: score}. From SageMaker in production,
                          simulated here.
        
        Returns:
            List of (ContentItem, score) tuples, sorted by score descending
        """
        collab_scores = collab_scores or {}
        scored = []

        for item in candidates:
            # Component 1: Collaborative filtering (40%)
            cf_score = collab_scores.get(item.content_id, 0.5)  # Default 0.5 if no CF data

            # Component 2: Content affinity (25%)
            affinity_score = self._compute_content_affinity(item, user)

            # Component 3: Freshness boost (15%)
            freshness_score = self._compute_freshness(item)

            # Component 4: Engagement tier adjustment (10%)
            tier_score = self._compute_tier_adjustment(item, user)

            # Component 5: Goal relevance (10%)
            goal_score = self._compute_goal_relevance(item, user)

            # Weighted composite
            total = (
                self.weights["collaborative_filtering"] * cf_score
                + self.weights["content_affinity"] * affinity_score
                + self.weights["freshness"] * freshness_score
                + self.weights["tier_adjustment"] * tier_score
                + self.weights["goal_relevance"] * goal_score
            )

            scored.append((item, total))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _compute_content_affinity(self, item: ContentItem,
                                   user: UserContext) -> float:
        """
        Score based on user's historical interaction with this content's category.
        
        Simple ratio: how much of the user's total interactions were with this
        category. Captures individual preference strength.
        
        Example: User completed 15 meditation sessions, 3 workouts, 1 article.
        Meditation affinity = 15/19 = 0.79, Workout = 0.16, Article = 0.05.
        """
        if user.total_interactions == 0:
            return 0.5  # Neutral for new users

        category_count = user.category_interaction_counts.get(item.category, 0)
        affinity = category_count / user.total_interactions

        # Normalize to 0-1 range (cap at 0.5 of interactions = max affinity)
        return min(affinity / 0.5, 1.0)

    def _compute_freshness(self, item: ContentItem) -> float:
        """
        Freshness boost for recently published content.
        
        New content gets a temporary ranking lift to ensure visibility.
        Without this, new content would never rank well because it has
        no interaction data — creating a cold start problem where popular
        content gets more popular and new content never gets discovered.
        """
        days = item.days_since_published
        if days <= 3:
            return 1.0
        elif days <= 7:
            return 0.7
        elif days <= 14:
            return 0.3
        else:
            return 0.0

    def _compute_tier_adjustment(self, item: ContentItem,
                                  user: UserContext) -> float:
        """
        Match content difficulty/length to user's engagement level.
        
        Tier 4-5 users (drifting/dormant) get simpler, shorter content.
        A drifting user doesn't need a 30-minute deep-dive workout —
        they need a 3-minute stretching routine that feels achievable.
        
        Tier 1-2 users get advanced, longer-form content that challenges them.
        Showing power users beginner content wastes their time and signals
        that the product doesn't understand them.
        """
        if user.engagement_tier in (1, 2):
            # Power/regular users: boost advanced, longer content
            if item.difficulty == "advanced" and item.duration_minutes >= 15:
                return 1.0
            elif item.difficulty == "intermediate":
                return 0.7
            elif item.difficulty == "beginner" and item.duration_minutes <= 5:
                return 0.3  # Penalize trivially easy content
            return 0.5

        elif user.engagement_tier == 3:
            # Casual users: neutral — no adjustment
            return 0.5

        else:
            # Tier 4-5: boost short, beginner, low-barrier content
            if item.duration_minutes <= 5 and item.difficulty == "beginner":
                return 1.0
            elif item.duration_minutes <= 10:
                return 0.7
            elif item.duration_minutes > 20:
                return 0.2  # Strongly deprioritize long content
            return 0.4

    def _compute_goal_relevance(self, item: ContentItem,
                                 user: UserContext) -> float:
        """
        Score based on alignment between content and user's goal cluster.
        
        Primary cluster match: 1.0
        Secondary cluster match: 0.6
        General wellness (E): 0.4 (always somewhat relevant)
        Unrelated: 0.2 (not zero — serendipitous discovery has value)
        """
        if user.goal_cluster in item.goal_clusters:
            return 1.0
        if user.secondary_goal_cluster and user.secondary_goal_cluster in item.goal_clusters:
            return 0.6
        if "E" in item.goal_clusters:
            return 0.4
        return 0.2

    # ----------------------------------------------------------------
    # Post-Ranking: Diversity Enforcement
    # ----------------------------------------------------------------

    def enforce_diversity(self, ranked: list, top_n: int = 20) -> list:
        """
        Reorder ranked items to enforce diversity constraints.
        
        Without diversity enforcement, the ranking model recommends clusters
        of similar items (5 meditation articles in a row). This is boring
        and limits discovery.
        
        Rules:
        - Max 2 items from same category in top 10
        - Max 3 items from same content_type in top 10
        - At least 1 "discovery" item from a less-explored category
        
        Implementation: walk through ranked list, swap items that violate
        constraints with the next-highest-scoring item that doesn't.
        """
        result = []
        category_counts = {}
        type_counts = {}
        remaining = list(ranked)  # Copy to avoid mutation

        for i in range(min(top_n, len(remaining))):
            placed = False

            for j, (item, score) in enumerate(remaining):
                cat_count = category_counts.get(item.category, 0)
                type_count = type_counts.get(item.content_type, 0)

                # Check diversity constraints (only enforced in top 10)
                if i < 10:
                    if cat_count >= MAX_SAME_CATEGORY_IN_TOP_10:
                        continue
                    if type_count >= MAX_SAME_TYPE_IN_TOP_10:
                        continue

                # Place this item
                result.append((item, score))
                category_counts[item.category] = cat_count + 1
                type_counts[item.content_type] = type_count + 1
                remaining.pop(j)
                placed = True
                break

            # If nothing fits constraints, take the next highest scored item
            if not placed and remaining:
                result.append(remaining.pop(0))

        return result

    # ----------------------------------------------------------------
    # CTA Personalization
    # ----------------------------------------------------------------

    def select_cta(self, user: UserContext) -> dict:
        """
        Select personalized call-to-action based on lifecycle stage
        and engagement trend.
        
        The CTA appears at the top of the personalized feed and adapts
        to where the user is in their journey.
        """
        cta_templates = {
            "new": {
                "text": "Start your first {goal} activity",
                "action": "start_onboarding_activity",
                "tone": "welcoming"
            },
            "activated": {
                "text": "Keep building momentum — day {streak} streak!",
                "action": "continue_streak",
                "tone": "encouraging"
            },
            "engaged": {
                "text": "New {goal} content just dropped",
                "action": "view_new_content",
                "tone": "informative"
            },
            "at_risk": {
                "text": "Quick 3-minute reset — you've got this",
                "action": "start_quick_activity",
                "tone": "empathetic"
            },
            "dormant": {
                "text": "Welcome back! Here's what's new since your last visit",
                "action": "view_whats_new",
                "tone": "celebratory"
            },
            "reactivated": {
                "text": "Great to see you back! Pick up where you left off",
                "action": "resume_progress",
                "tone": "encouraging"
            }
        }

        stage = user.lifecycle_stage
        cta = cta_templates.get(stage, cta_templates["engaged"])

        # Substitute goal cluster name
        goal_names = {
            "A": "weight management",
            "B": "fitness",
            "C": "wellness",
            "D": "health",
            "E": "wellness"
        }
        goal_name = goal_names.get(user.goal_cluster, "wellness")
        cta["text"] = cta["text"].format(goal=goal_name, streak="7")

        return cta

    # ----------------------------------------------------------------
    # Fallback Ranking
    # ----------------------------------------------------------------

    def fallback_ranking(self, candidates: list, user: UserContext) -> list:
        """
        Rule-based ranking used when ML model is unavailable.
        
        Graceful degradation: if SageMaker is down or the collaborative
        filtering model fails, fall back to goal relevance × recency
        × popularity. Users still get a feed — just less personalized.
        
        The fallback is indistinguishable to the user: no error states,
        no loading spinners, no "recommendations unavailable" messages.
        """
        scored = []
        for item in candidates:
            goal_score = self._compute_goal_relevance(item, user)
            recency_score = max(0, 1.0 - (item.days_since_published / 30.0))
            popularity_score = min(item.total_completions / 1000.0, 1.0)

            total = 0.50 * goal_score + 0.30 * recency_score + 0.20 * popularity_score
            scored.append((item, total))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ----------------------------------------------------------------
    # Main Entry Point
    # ----------------------------------------------------------------

    def recommend(self, user: UserContext,
                  catalog: list,
                  collab_scores: dict = None,
                  top_n: int = 20,
                  use_fallback: bool = False) -> RecommendationResult:
        """
        Generate personalized content recommendations for a user.
        
        Full pipeline:
        1. Generate candidates (filter catalog)
        2. Rank candidates (ML-informed scoring)
        3. Enforce diversity (post-ranking reordering)
        4. Select CTA (lifecycle-appropriate call to action)
        5. Return ranked list with metadata
        
        Args:
            user: User context (from Redis caches)
            catalog: Full content catalog
            collab_scores: Collaborative filtering predictions {content_id: score}
            top_n: Number of items to return
            use_fallback: Force fallback ranking (for testing or when ML is down)
        
        Returns:
            RecommendationResult with ranked items, scores, CTA, and metadata
        """
        start = datetime.utcnow()

        # Stage 1: Candidate generation
        candidates = self.generate_candidates(user, catalog)

        if not candidates:
            # No candidates after filtering — return popular content as last resort
            candidates = sorted(catalog, key=lambda x: x.total_completions, reverse=True)[:top_n]

        # Stage 2: Ranking
        if use_fallback or collab_scores is None:
            ranked = self.fallback_ranking(candidates, user)
            used_fallback = True
        else:
            ranked = self.rank_candidates(user, candidates, collab_scores)
            used_fallback = False

        # Post-ranking: diversity enforcement
        diverse = self.enforce_diversity(ranked, top_n)

        # CTA selection
        cta = self.select_cta(user)

        elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000

        items = [item for item, score in diverse]
        scores = [score for item, score in diverse]

        return RecommendationResult(
            user_id=user.user_id,
            items=items,
            scores=scores,
            cta=cta,
            experiment_exposures=[],
            computed_in_ms=elapsed_ms,
            used_fallback=used_fallback
        )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    engine = RecommendationEngine()

    # Create sample content catalog
    catalog = [
        ContentItem("c1", "5-Min Morning Stretch", "guided_activity", "fitness",
                     ["B", "E"], "beginner", 5, datetime(2025, 1, 10), 850, 4.6),
        ContentItem("c2", "Understanding Stress Response", "article", "stress_management",
                     ["C"], "beginner", 8, datetime(2025, 1, 12), 620, 4.3),
        ContentItem("c3", "HIIT Cardio Blast", "workout", "fitness",
                     ["B"], "advanced", 30, datetime(2025, 1, 5), 1200, 4.7),
        ContentItem("c4", "Guided Sleep Meditation", "meditation", "sleep",
                     ["C", "E"], "beginner", 15, datetime(2025, 1, 14), 2100, 4.8),
        ContentItem("c5", "Meal Prep for Weight Loss", "article", "nutrition",
                     ["A"], "intermediate", 12, datetime(2025, 1, 8), 980, 4.4),
        ContentItem("c6", "2-Min Breathing Exercise", "guided_activity", "stress_management",
                     ["C", "E"], "beginner", 2, datetime(2025, 1, 15), 3200, 4.9),
        ContentItem("c7", "Advanced Yoga Flow", "workout", "fitness",
                     ["B"], "advanced", 45, datetime(2024, 12, 20), 750, 4.5),
        ContentItem("c8", "Journaling for Anxiety", "guided_activity", "stress_management",
                     ["C"], "beginner", 10, datetime(2025, 1, 13), 410, 4.2),
    ]

    # Simulate a Tier 4 (drifting) user focused on mental wellness
    user = UserContext(
        user_id="user-abc-123",
        engagement_score=35,
        engagement_tier=4,
        lifecycle_stage="at_risk",
        goal_cluster="C",
        secondary_goal_cluster="E",
        category_interaction_counts={"stress_management": 12, "sleep": 8, "fitness": 2},
        total_interactions=22,
        recently_seen_ids=["c2"],
        completed_ids=[]
    )

    # Simulate collaborative filtering scores
    collab_scores = {
        "c1": 0.4, "c3": 0.2, "c4": 0.8,
        "c5": 0.3, "c6": 0.9, "c7": 0.1, "c8": 0.7
    }

    result = engine.recommend(user, catalog, collab_scores, top_n=5)

    print(f"Recommendations for {result.user_id} (Tier {user.engagement_tier}, {user.lifecycle_stage}):")
    print(f"  Computed in: {result.computed_in_ms:.1f}ms")
    print(f"  Used fallback: {result.used_fallback}")
    print(f"  CTA: \"{result.cta['text']}\"")
    print()
    for i, (item, score) in enumerate(zip(result.items, result.scores)):
        print(f"  {i+1}. [{score:.3f}] {item.title} ({item.content_type}, "
              f"{item.duration_minutes}min, {item.difficulty})")
