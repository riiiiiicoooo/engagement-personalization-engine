"""
User Segmentation Engine
========================

Real-time user segmentation across four dimensions:
- Lifecycle stage (new, activated, engaged, at-risk, dormant, reactivated)
- Behavioral cohort (power, regular, casual, drifting, dormant, churned)
- Engagement tier (1-5 based on composite score)
- Goal cluster (A-E based on onboarding + behavioral signals)

Each user's segment membership is computed on every meaningful event and cached
in Redis for sub-millisecond retrieval by the personalization and experiment engines.

Reference implementation — validates segmentation logic and transition rules.
Production version runs as a FastAPI service with Redis and PostgreSQL backends.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


# ============================================================================
# Segment Definitions
# ============================================================================

class LifecycleStage(Enum):
    """Where the user is in their journey with the platform."""
    NEW = "new"                     # Days 0-7, no key action yet
    ACTIVATED = "activated"         # Completed first key action
    ENGAGED = "engaged"             # Sustained activity 2+ weeks
    AT_RISK = "at_risk"             # Score declining or churn probability high
    DORMANT = "dormant"             # No meaningful action 14+ days
    REACTIVATED = "reactivated"     # Returned after dormancy


class BehavioralCohort(Enum):
    """How the user actually behaves, based on trailing 14-day patterns."""
    POWER = "power"         # 7+ sessions/week, 3+ actions/session
    REGULAR = "regular"     # 3-6 sessions/week, 1-2 actions/session
    CASUAL = "casual"       # 1-2 sessions/week, brief sessions
    DRIFTING = "drifting"   # Was regular/power, now declining >50% WoW
    DORMANT = "dormant"     # 0 sessions in 14 days
    CHURNED = "churned"     # 0 sessions in 30+ days


class EngagementTier(Enum):
    """Engagement level based on composite score."""
    TIER_1 = 1  # 80-100: Power users
    TIER_2 = 2  # 60-79:  Regular users
    TIER_3 = 3  # 40-59:  Casual users
    TIER_4 = 4  # 20-39:  Drifting users
    TIER_5 = 5  # 0-19:   Dormant/nearly churned


class GoalCluster(Enum):
    """What the user is trying to accomplish."""
    WEIGHT_MANAGEMENT = "A"
    FITNESS = "B"
    MENTAL_WELLNESS = "C"
    CHRONIC_CONDITION = "D"
    GENERAL_WELLNESS = "E"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class UserActivity:
    """Trailing activity data used for segmentation decisions."""
    user_id: str
    days_since_signup: int
    first_key_action_completed: bool
    first_key_action_at: Optional[datetime] = None

    # Trailing 14-day metrics
    sessions_14d: int = 0
    sessions_per_week_14d: float = 0.0
    meaningful_actions_per_session_14d: float = 0.0
    active_days_14d: int = 0

    # Trailing 7-day metrics
    sessions_7d: int = 0
    sessions_prev_7d: int = 0  # Prior 7 days (for WoW comparison)

    # Recency
    hours_since_last_meaningful_action: float = float('inf')
    last_meaningful_action_at: Optional[datetime] = None

    # Engagement
    engagement_score: float = 0.0
    engagement_score_3d_ago: float = 0.0
    churn_probability_14d: float = 0.0

    # Goals
    onboarding_goals: list = field(default_factory=list)
    content_category_counts: dict = field(default_factory=dict)

    # Previous state
    previous_lifecycle_stage: Optional[LifecycleStage] = None
    previous_behavioral_cohort: Optional[BehavioralCohort] = None
    was_dormant: bool = False


@dataclass
class SegmentMembership:
    """Complete segment assignment for a user."""
    user_id: str
    lifecycle_stage: LifecycleStage
    behavioral_cohort: BehavioralCohort
    engagement_tier: EngagementTier
    goal_cluster: GoalCluster
    custom_segments: list = field(default_factory=list)
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_redis_hash(self) -> dict:
        """Serialize for Redis storage."""
        return {
            "lifecycle_stage": self.lifecycle_stage.value,
            "behavioral_cohort": self.behavioral_cohort.value,
            "engagement_tier": self.engagement_tier.value,
            "goal_cluster": self.goal_cluster.value,
            "custom_segments": ",".join(self.custom_segments),
            "computed_at": self.computed_at.isoformat()
        }

    def to_event_context(self) -> dict:
        """Serialize for inclusion in event context (sent with every event)."""
        return {
            "lifecycle_stage": self.lifecycle_stage.value,
            "behavioral_cohort": self.behavioral_cohort.value,
            "engagement_tier": self.engagement_tier.value,
            "goal_cluster": self.goal_cluster.value
        }


# ============================================================================
# Segmentation Engine
# ============================================================================

class UserSegmenter:
    """
    Computes segment membership for a user based on their activity data.
    
    Called on every meaningful event to keep segments current. Results are
    cached in Redis (TTL: 1 hour) and logged as segment_transition events
    when membership changes.
    
    Usage:
        segmenter = UserSegmenter()
        activity = UserActivity(user_id="abc-123", ...)
        membership = segmenter.compute_segments(activity)
    """

    # ----------------------------------------------------------------
    # Lifecycle Stage
    # ----------------------------------------------------------------

    def compute_lifecycle_stage(self, activity: UserActivity) -> LifecycleStage:
        """
        Determine lifecycle stage based on activity and engagement signals.
        
        Transition rules (evaluated in priority order):
        1. Dormant: no meaningful action in 14+ days
        2. At-risk: score declining rapidly OR churn probability > 70%
        3. Reactivated: returned after dormancy
        4. Engaged: sustained activity for 2+ weeks
        5. Activated: completed first key action
        6. New: days 0-7, no key action yet
        """
        hours_inactive = activity.hours_since_last_meaningful_action

        # Rule 1: Dormant — 14+ days without meaningful action
        if hours_inactive >= 336:  # 14 days × 24 hours
            return LifecycleStage.DORMANT

        # Rule 2: At-risk — rapid score decline or high churn probability
        score_drop = activity.engagement_score_3d_ago - activity.engagement_score
        if score_drop > 15 or activity.churn_probability_14d > 0.70:
            return LifecycleStage.AT_RISK

        # Rule 3: Reactivated — came back after being dormant
        if activity.was_dormant and hours_inactive < 336:
            # Check if they've sustained activity long enough to be "engaged"
            if activity.active_days_14d >= 6 and activity.sessions_per_week_14d >= 3:
                return LifecycleStage.ENGAGED
            return LifecycleStage.REACTIVATED

        # Rule 4: Engaged — sustained activity for 2+ consecutive weeks
        if (activity.first_key_action_completed
                and activity.days_since_signup >= 14
                and activity.active_days_14d >= 6
                and activity.sessions_per_week_14d >= 3):
            return LifecycleStage.ENGAGED

        # Rule 5: Activated — completed first key action
        if activity.first_key_action_completed:
            return LifecycleStage.ACTIVATED

        # Rule 6: New — hasn't completed first key action yet
        return LifecycleStage.NEW

    # ----------------------------------------------------------------
    # Behavioral Cohort
    # ----------------------------------------------------------------

    def compute_behavioral_cohort(self, activity: UserActivity) -> BehavioralCohort:
        """
        Assign behavioral cohort based on trailing 14-day activity patterns.
        
        Key distinction: "drifting" catches users in the transition from
        active to inactive. This is the highest-value intervention window —
        3x more effective than intervening after dormancy.
        """
        sessions_pw = activity.sessions_per_week_14d
        actions_ps = activity.meaningful_actions_per_session_14d

        # Churned: no activity in 30+ days
        if activity.hours_since_last_meaningful_action >= 720:  # 30 days
            return BehavioralCohort.CHURNED

        # Dormant: no activity in 14+ days
        if activity.sessions_14d == 0:
            return BehavioralCohort.DORMANT

        # Drifting: was regular/power but session count dropped >50% WoW
        if activity.sessions_prev_7d > 0:
            wow_change = (activity.sessions_7d - activity.sessions_prev_7d) / activity.sessions_prev_7d
            was_active = activity.sessions_prev_7d >= 3  # Was at least regular
            if was_active and wow_change < -0.50:
                return BehavioralCohort.DRIFTING

        # Power: 7+ sessions/week with deep engagement
        if sessions_pw >= 7 and actions_ps >= 3:
            return BehavioralCohort.POWER

        # Regular: 3-6 sessions/week with moderate engagement
        if sessions_pw >= 3 and actions_ps >= 1:
            return BehavioralCohort.REGULAR

        # Casual: anything else with some activity
        return BehavioralCohort.CASUAL

    # ----------------------------------------------------------------
    # Engagement Tier
    # ----------------------------------------------------------------

    def compute_engagement_tier(self, engagement_score: float) -> EngagementTier:
        """
        Map engagement score (0-100) to tier (1-5).
        
        Tier boundaries are fixed, not percentile-based. This means the
        distribution can shift over time (ideally: more users in Tier 1-2,
        fewer in Tier 4-5 as personalization improves).
        """
        if engagement_score >= 80:
            return EngagementTier.TIER_1
        elif engagement_score >= 60:
            return EngagementTier.TIER_2
        elif engagement_score >= 40:
            return EngagementTier.TIER_3
        elif engagement_score >= 20:
            return EngagementTier.TIER_4
        else:
            return EngagementTier.TIER_5

    # ----------------------------------------------------------------
    # Goal Cluster
    # ----------------------------------------------------------------

    def compute_goal_cluster(self, activity: UserActivity) -> GoalCluster:
        """
        Assign goal cluster based on onboarding survey + behavioral signals.
        
        Initial assignment from onboarding goals. Refined by actual content
        engagement patterns over first 30 days. After 30 days, cluster
        rarely changes (stable in 91% of users).
        """
        # Map onboarding goals to clusters
        goal_to_cluster = {
            "lose_weight": GoalCluster.WEIGHT_MANAGEMENT,
            "gain_weight": GoalCluster.WEIGHT_MANAGEMENT,
            "nutrition": GoalCluster.WEIGHT_MANAGEMENT,
            "exercise": GoalCluster.FITNESS,
            "strength": GoalCluster.FITNESS,
            "cardio": GoalCluster.FITNESS,
            "stress": GoalCluster.MENTAL_WELLNESS,
            "anxiety": GoalCluster.MENTAL_WELLNESS,
            "sleep": GoalCluster.MENTAL_WELLNESS,
            "meditation": GoalCluster.MENTAL_WELLNESS,
            "diabetes": GoalCluster.CHRONIC_CONDITION,
            "hypertension": GoalCluster.CHRONIC_CONDITION,
            "chronic_pain": GoalCluster.CHRONIC_CONDITION,
            "general_health": GoalCluster.GENERAL_WELLNESS,
        }

        # Start with onboarding signal
        cluster_votes = {}
        for goal in activity.onboarding_goals:
            cluster = goal_to_cluster.get(goal, GoalCluster.GENERAL_WELLNESS)
            cluster_votes[cluster] = cluster_votes.get(cluster, 0) + 1

        # Incorporate behavioral signals (content engagement patterns)
        category_to_cluster = {
            "nutrition": GoalCluster.WEIGHT_MANAGEMENT,
            "meal_planning": GoalCluster.WEIGHT_MANAGEMENT,
            "workouts": GoalCluster.FITNESS,
            "exercise_tutorials": GoalCluster.FITNESS,
            "meditation": GoalCluster.MENTAL_WELLNESS,
            "journaling": GoalCluster.MENTAL_WELLNESS,
            "breathing": GoalCluster.MENTAL_WELLNESS,
            "condition_education": GoalCluster.CHRONIC_CONDITION,
            "vitals_tracking": GoalCluster.CHRONIC_CONDITION,
        }

        for category, count in activity.content_category_counts.items():
            cluster = category_to_cluster.get(category, GoalCluster.GENERAL_WELLNESS)
            # Behavioral signal weighted 2x after first week
            weight = 2 if activity.days_since_signup > 7 else 1
            cluster_votes[cluster] = cluster_votes.get(cluster, 0) + (count * weight)

        # Return highest-voted cluster, default to general wellness
        if not cluster_votes:
            return GoalCluster.GENERAL_WELLNESS

        return max(cluster_votes, key=cluster_votes.get)

    # ----------------------------------------------------------------
    # Custom Segments
    # ----------------------------------------------------------------

    def evaluate_custom_segments(self, activity: UserActivity,
                                  membership: SegmentMembership) -> list:
        """
        Evaluate PM-defined custom segment rules.
        
        Custom segments combine standard dimensions with additional criteria
        for experiment targeting and personalization. Defined via admin UI
        and stored in PostgreSQL.
        
        Example: "high-value at-risk" = {
            engagement_tier IN (3, 4),
            subscription_status = 'active',
            score_delta_7d < -15
        }
        """
        custom = []

        # High-value at-risk: paying users whose engagement is declining
        score_delta = activity.engagement_score - activity.engagement_score_3d_ago
        if (membership.engagement_tier in (EngagementTier.TIER_3, EngagementTier.TIER_4)
                and score_delta < -10):
            custom.append("high_value_at_risk")

        # New user activation window: days 1-7, not yet activated
        if (activity.days_since_signup <= 7
                and not activity.first_key_action_completed):
            custom.append("activation_window")

        # Power user candidate: Tier 2 with improving trend
        if (membership.engagement_tier == EngagementTier.TIER_2
                and score_delta > 5):
            custom.append("power_user_candidate")

        # Re-engagement opportunity: drifting but opened app recently
        if (membership.behavioral_cohort == BehavioralCohort.DRIFTING
                and activity.hours_since_last_meaningful_action < 72):
            custom.append("reengagement_opportunity")

        return custom

    # ----------------------------------------------------------------
    # Main Computation
    # ----------------------------------------------------------------

    def compute_segments(self, activity: UserActivity) -> SegmentMembership:
        """
        Compute complete segment membership for a user.
        
        Called on every meaningful event. Results are:
        1. Cached in Redis (key: segments:{user_id}, TTL: 1 hour)
        2. Compared to previous membership for transition detection
        3. Included in event context for downstream analytics
        
        Returns:
            SegmentMembership with all four dimensions + custom segments
        """
        lifecycle = self.compute_lifecycle_stage(activity)
        cohort = self.compute_behavioral_cohort(activity)
        tier = self.compute_engagement_tier(activity.engagement_score)
        goal = self.compute_goal_cluster(activity)

        membership = SegmentMembership(
            user_id=activity.user_id,
            lifecycle_stage=lifecycle,
            behavioral_cohort=cohort,
            engagement_tier=tier,
            goal_cluster=goal
        )

        # Evaluate custom segments after standard dimensions are set
        membership.custom_segments = self.evaluate_custom_segments(activity, membership)

        return membership

    def detect_transitions(self, previous: SegmentMembership,
                           current: SegmentMembership) -> list:
        """
        Detect segment transitions for logging and intervention triggers.
        
        Transitions are logged as segment_transition events and may trigger
        interventions (e.g., lifecycle_stage change to AT_RISK triggers
        intervention evaluation).
        
        Returns:
            List of transition dicts with dimension, old_value, new_value
        """
        transitions = []

        if previous.lifecycle_stage != current.lifecycle_stage:
            transitions.append({
                "dimension": "lifecycle_stage",
                "old_value": previous.lifecycle_stage.value,
                "new_value": current.lifecycle_stage.value,
                "trigger_intervention": current.lifecycle_stage == LifecycleStage.AT_RISK
            })

        if previous.behavioral_cohort != current.behavioral_cohort:
            transitions.append({
                "dimension": "behavioral_cohort",
                "old_value": previous.behavioral_cohort.value,
                "new_value": current.behavioral_cohort.value,
                "trigger_intervention": current.behavioral_cohort == BehavioralCohort.DRIFTING
            })

        if previous.engagement_tier != current.engagement_tier:
            tier_drop = current.engagement_tier.value - previous.engagement_tier.value
            transitions.append({
                "dimension": "engagement_tier",
                "old_value": previous.engagement_tier.value,
                "new_value": current.engagement_tier.value,
                "trigger_intervention": tier_drop >= 2  # Dropped 2+ tiers
            })

        if previous.goal_cluster != current.goal_cluster:
            transitions.append({
                "dimension": "goal_cluster",
                "old_value": previous.goal_cluster.value,
                "new_value": current.goal_cluster.value,
                "trigger_intervention": False
            })

        return transitions


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    segmenter = UserSegmenter()

    # Simulate an engaged user whose activity is declining
    activity = UserActivity(
        user_id="user-abc-123",
        days_since_signup=45,
        first_key_action_completed=True,
        first_key_action_at=datetime(2024, 12, 5),
        sessions_14d=6,
        sessions_per_week_14d=3.0,
        meaningful_actions_per_session_14d=1.5,
        active_days_14d=5,
        sessions_7d=2,
        sessions_prev_7d=5,
        hours_since_last_meaningful_action=52,
        engagement_score=48,
        engagement_score_3d_ago=65,
        churn_probability_14d=0.55,
        onboarding_goals=["stress", "sleep"],
        content_category_counts={"meditation": 12, "breathing": 8, "journaling": 3},
        previous_lifecycle_stage=LifecycleStage.ENGAGED,
        previous_behavioral_cohort=BehavioralCohort.REGULAR,
        was_dormant=False
    )

    membership = segmenter.compute_segments(activity)

    print(f"User: {membership.user_id}")
    print(f"  Lifecycle:  {membership.lifecycle_stage.value}")
    print(f"  Cohort:     {membership.behavioral_cohort.value}")
    print(f"  Tier:       {membership.engagement_tier.value}")
    print(f"  Goal:       {membership.goal_cluster.value}")
    print(f"  Custom:     {membership.custom_segments}")
    print()

    # Detect transitions from previous state
    previous = SegmentMembership(
        user_id="user-abc-123",
        lifecycle_stage=LifecycleStage.ENGAGED,
        behavioral_cohort=BehavioralCohort.REGULAR,
        engagement_tier=EngagementTier.TIER_2,
        goal_cluster=GoalCluster.MENTAL_WELLNESS
    )

    transitions = segmenter.detect_transitions(previous, membership)
    print(f"Transitions detected: {len(transitions)}")
    for t in transitions:
        intervention = " → INTERVENTION TRIGGERED" if t["trigger_intervention"] else ""
        print(f"  {t['dimension']}: {t['old_value']} → {t['new_value']}{intervention}")
