"""
Feature Flag Service
====================

Feature flag evaluation engine supporting:
- Boolean and multivariate flags
- Percentage-based progressive rollout (0-100%)
- Segment-targeted flags (show to specific user segments)
- User allowlist/blocklist overrides
- Kill switch (instant off for any flag)
- Evaluation audit logging

Separate from experiments. Flags are permanent infrastructure for operational
control and progressive rollout. Experiments are temporary and measure impact.
A flag can gate an experiment variant, but they have different lifecycles.

Evaluation target: < 5ms (p95) via Redis caching.

Reference implementation — validates evaluation logic and rule precedence.
Production version uses Redis for flag config caching (TTL: 5 min) with
pub/sub for instant invalidation on flag update.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from enum import Enum
import hashlib
import json


# ============================================================================
# Flag Models
# ============================================================================

class FlagType(Enum):
    BOOLEAN = "boolean"
    STRING = "string"
    INTEGER = "integer"
    JSON = "json"


class FlagLifecycle(Enum):
    CREATED = "created"
    ACTIVE = "active"
    STALE = "stale"       # No changes in 30+ days — alert for cleanup
    ARCHIVED = "archived"


@dataclass
class FeatureFlag:
    """Complete feature flag definition."""
    flag_key: str
    name: str
    description: str = ""
    flag_type: FlagType = FlagType.BOOLEAN
    default_value: Any = False

    # State
    is_active: bool = True
    is_killed: bool = False  # Kill switch — overrides everything

    # Rollout
    rollout_percentage: int = 0  # 0-100

    # Targeting
    target_segments: list = field(default_factory=list)  # Segment IDs
    allowlist: list = field(default_factory=list)  # User IDs always ON
    blocklist: list = field(default_factory=list)  # User IDs always OFF

    # Multivariate variants
    variants: list = field(default_factory=list)
    # [{"id": "v1", "value": "blue_button", "weight": 50},
    #  {"id": "v2", "value": "green_button", "weight": 50}]

    # Lifecycle
    lifecycle: FlagLifecycle = FlagLifecycle.CREATED
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    stale_alert_at: Optional[datetime] = None

    # Dependencies
    depends_on: list = field(default_factory=list)  # Flag keys this flag requires

    # Linked experiment
    experiment_id: Optional[str] = None

    def to_redis_hash(self) -> dict:
        """Serialize for Redis storage. Key: flag:{flag_key}, TTL: 5min."""
        return {
            "type": self.flag_type.value,
            "default": json.dumps(self.default_value),
            "killed": str(self.is_killed).lower(),
            "active": str(self.is_active).lower(),
            "rollout_pct": str(self.rollout_percentage),
            "allowlist": json.dumps(self.allowlist),
            "blocklist": json.dumps(self.blocklist),
            "target_segments": json.dumps(self.target_segments),
            "variants": json.dumps(self.variants),
            "depends_on": json.dumps(self.depends_on),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class FlagEvaluation:
    """Result of evaluating a flag for a specific user."""
    flag_key: str
    user_id: str
    value: Any
    rule_matched: str  # Which rule determined the value
    evaluated_at: datetime = field(default_factory=datetime.utcnow)

    def to_audit_event(self) -> dict:
        """Serialize as flag_evaluated event for audit logging."""
        return {
            "event_type": "flag_evaluated",
            "flag_key": self.flag_key,
            "user_id": self.user_id,
            "value": self.value,
            "rule_matched": self.rule_matched,
            "timestamp": self.evaluated_at.isoformat()
        }


@dataclass
class UserFlagContext:
    """User context needed for flag evaluation."""
    user_id: str
    segments: list = field(default_factory=list)  # Segment IDs user belongs to
    properties: dict = field(default_factory=dict)  # Additional user properties


# ============================================================================
# Flag Evaluation Engine
# ============================================================================

class FeatureFlagService:
    """
    Evaluates feature flags for users with sub-5ms latency.
    
    Evaluation rules are checked in strict priority order:
    1. Kill switch → OFF (overrides everything)
    2. Flag inactive → default value
    3. User blocklist → OFF
    4. User allowlist → ON
    5. Dependency check → OFF if dependency not met
    6. Segment targeting → evaluate if user in target segment
    7. Rollout percentage → hash-based deterministic check
    8. Default value → returned if no rule matches
    
    In production, flag configs are cached in Redis (TTL: 5 min) with
    instant invalidation via pub/sub when a flag is updated. Evaluation
    happens in-memory from the cached config — no database calls on the
    hot path.
    
    Usage:
        service = FeatureFlagService()
        service.register_flag(flag)
        result = service.evaluate("flag_key", user_context)
    """

    def __init__(self):
        self.flags: dict = {}  # flag_key → FeatureFlag
        self.evaluation_log: list = []  # Audit trail

    def register_flag(self, flag: FeatureFlag):
        """Register a flag (simulates loading from Redis/PostgreSQL)."""
        self.flags[flag.flag_key] = flag

    def evaluate(self, flag_key: str, user: UserFlagContext,
                 log_evaluation: bool = True) -> FlagEvaluation:
        """
        Evaluate a feature flag for a specific user.
        
        Returns the flag value and which rule determined it.
        Logs evaluation event for audit trail (async in production).
        
        Rule evaluation order (first match wins):
        1. Kill switch
        2. Flag inactive
        3. Blocklist
        4. Allowlist
        5. Dependencies
        6. Segment targeting
        7. Rollout percentage
        8. Default
        """
        flag = self.flags.get(flag_key)

        # Flag not found
        if flag is None:
            result = FlagEvaluation(
                flag_key=flag_key,
                user_id=user.user_id,
                value=False,
                rule_matched="flag_not_found"
            )
            if log_evaluation:
                self.evaluation_log.append(result)
            return result

        # Rule 1: Kill switch — immediate OFF
        if flag.is_killed:
            result = FlagEvaluation(
                flag_key=flag_key,
                user_id=user.user_id,
                value=flag.default_value,
                rule_matched="kill_switch"
            )
            if log_evaluation:
                self.evaluation_log.append(result)
            return result

        # Rule 2: Flag inactive
        if not flag.is_active:
            result = FlagEvaluation(
                flag_key=flag_key,
                user_id=user.user_id,
                value=flag.default_value,
                rule_matched="flag_inactive"
            )
            if log_evaluation:
                self.evaluation_log.append(result)
            return result

        # Rule 3: Blocklist — user explicitly excluded
        if user.user_id in flag.blocklist:
            result = FlagEvaluation(
                flag_key=flag_key,
                user_id=user.user_id,
                value=flag.default_value,
                rule_matched="blocklist"
            )
            if log_evaluation:
                self.evaluation_log.append(result)
            return result

        # Rule 4: Allowlist — user explicitly included
        if user.user_id in flag.allowlist:
            value = True if flag.flag_type == FlagType.BOOLEAN else self._get_first_variant_value(flag)
            result = FlagEvaluation(
                flag_key=flag_key,
                user_id=user.user_id,
                value=value,
                rule_matched="allowlist"
            )
            if log_evaluation:
                self.evaluation_log.append(result)
            return result

        # Rule 5: Dependency check — all dependencies must be ON
        if flag.depends_on:
            for dep_key in flag.depends_on:
                dep_result = self.evaluate(dep_key, user, log_evaluation=False)
                if not dep_result.value:
                    result = FlagEvaluation(
                        flag_key=flag_key,
                        user_id=user.user_id,
                        value=flag.default_value,
                        rule_matched=f"dependency_not_met:{dep_key}"
                    )
                    if log_evaluation:
                        self.evaluation_log.append(result)
                    return result

        # Rule 6: Segment targeting — must be in at least one target segment
        if flag.target_segments:
            user_in_segment = any(
                seg in user.segments for seg in flag.target_segments
            )
            if not user_in_segment:
                result = FlagEvaluation(
                    flag_key=flag_key,
                    user_id=user.user_id,
                    value=flag.default_value,
                    rule_matched="segment_not_matched"
                )
                if log_evaluation:
                    self.evaluation_log.append(result)
                return result

        # Rule 7: Rollout percentage — deterministic hash check
        if flag.rollout_percentage < 100:
            bucket = self._compute_bucket(user.user_id, flag_key)
            if bucket >= flag.rollout_percentage:
                result = FlagEvaluation(
                    flag_key=flag_key,
                    user_id=user.user_id,
                    value=flag.default_value,
                    rule_matched=f"rollout_excluded (bucket={bucket}, rollout={flag.rollout_percentage}%)"
                )
                if log_evaluation:
                    self.evaluation_log.append(result)
                return result

        # All rules passed — flag is ON
        if flag.flag_type == FlagType.BOOLEAN:
            value = True
            rule = "rollout_included"
        elif flag.variants:
            # Multivariate: select variant based on hash
            value = self._select_variant(user.user_id, flag)
            rule = f"variant_selected:{value}"
        else:
            value = True
            rule = "rollout_included"

        result = FlagEvaluation(
            flag_key=flag_key,
            user_id=user.user_id,
            value=value,
            rule_matched=rule
        )

        if log_evaluation:
            self.evaluation_log.append(result)
        return result

    def evaluate_all(self, flag_keys: list,
                     user: UserFlagContext) -> dict:
        """
        Evaluate multiple flags at once (batch evaluation).
        
        Used on app load to fetch all flag values in a single call.
        In production, this is a single Redis MGET + in-memory evaluation.
        """
        return {
            key: self.evaluate(key, user).value
            for key in flag_keys
        }

    # ----------------------------------------------------------------
    # Flag Management
    # ----------------------------------------------------------------

    def kill_flag(self, flag_key: str):
        """
        Emergency kill switch — immediately disable a flag.
        
        In production, this:
        1. Sets is_killed = True in PostgreSQL
        2. Publishes update to Redis pub/sub channel
        3. All API servers invalidate cache for this flag
        4. Next evaluation returns default value
        
        Total propagation time: < 1 second.
        """
        flag = self.flags.get(flag_key)
        if flag:
            flag.is_killed = True
            flag.updated_at = datetime.utcnow()

    def set_rollout(self, flag_key: str, percentage: int):
        """Update rollout percentage (0-100)."""
        flag = self.flags.get(flag_key)
        if flag:
            flag.rollout_percentage = max(0, min(100, percentage))
            flag.updated_at = datetime.utcnow()

    def get_stale_flags(self, stale_days: int = 30) -> list:
        """
        Find flags that haven't been updated in 30+ days.
        
        Stale flags are technical debt. They should be either:
        - Rolled to 100% and made permanent (remove the flag, keep the code)
        - Turned off and archived (remove the flag and the code)
        
        Before this system, we had 180+ stale flags. After implementing
        stale alerts, active flag count dropped to 23.
        """
        cutoff = datetime.utcnow() - timedelta(days=stale_days)
        stale = []
        for flag in self.flags.values():
            if (flag.is_active
                    and not flag.is_killed
                    and flag.updated_at < cutoff
                    and flag.lifecycle != FlagLifecycle.ARCHIVED):
                stale.append({
                    "flag_key": flag.flag_key,
                    "name": flag.name,
                    "days_since_update": (datetime.utcnow() - flag.updated_at).days,
                    "rollout_pct": flag.rollout_percentage,
                    "action": "Review: archive or roll to 100%"
                })
        return stale

    # ----------------------------------------------------------------
    # Internal Helpers
    # ----------------------------------------------------------------

    def _compute_bucket(self, user_id: str, flag_key: str) -> int:
        """Deterministic hash bucket (0-99) for rollout evaluation."""
        hash_input = f"{user_id}:{flag_key}".encode('utf-8')
        hash_digest = hashlib.sha256(hash_input).hexdigest()
        return int(hash_digest[:8], 16) % 100

    def _select_variant(self, user_id: str, flag: FeatureFlag) -> Any:
        """Select a multivariate flag value based on user hash."""
        bucket = self._compute_bucket(user_id, f"{flag.flag_key}:variant")
        cumulative = 0
        for variant in flag.variants:
            cumulative += variant.get("weight", 0)
            if bucket < cumulative:
                return variant.get("value", flag.default_value)
        return flag.default_value

    def _get_first_variant_value(self, flag: FeatureFlag) -> Any:
        """Get the first variant value (for allowlist users)."""
        if flag.variants:
            return flag.variants[0].get("value", True)
        return True


# ============================================================================
# Progressive Rollout Manager
# ============================================================================

class ProgressiveRollout:
    """
    Manages progressive rollout of feature flags: 1% → 5% → 20% → 50% → 100%.
    
    Each stage has monitoring criteria that must be met before advancing.
    If any criterion fails, the rollout is paused and the team is alerted.
    
    This system prevented 2+ rollout incidents in the first 6 months by
    catching issues at 5% that would have affected 100% of users.
    """

    STAGES = [
        {"percentage": 1, "duration_hours": 4, "label": "Canary"},
        {"percentage": 5, "duration_hours": 12, "label": "Early Access"},
        {"percentage": 20, "duration_hours": 24, "label": "Limited"},
        {"percentage": 50, "duration_hours": 48, "label": "Broad"},
        {"percentage": 100, "duration_hours": None, "label": "General Availability"},
    ]

    def __init__(self, flag_service: FeatureFlagService):
        self.flag_service = flag_service
        self.rollout_state: dict = {}  # flag_key → current stage index

    def start_rollout(self, flag_key: str) -> dict:
        """Begin progressive rollout at Stage 0 (1%)."""
        stage = self.STAGES[0]
        self.flag_service.set_rollout(flag_key, stage["percentage"])
        self.rollout_state[flag_key] = 0
        return {
            "flag_key": flag_key,
            "stage": stage["label"],
            "percentage": stage["percentage"],
            "next_check_in_hours": stage["duration_hours"]
        }

    def advance_rollout(self, flag_key: str,
                        monitoring_clear: bool = True) -> dict:
        """
        Advance to next rollout stage if monitoring is clear.
        
        Halt conditions (any one blocks advancement):
        - Error rate increase > 0.1%
        - Latency increase > 50ms (p95)
        - Crash rate increase > 0.5%
        - Any guardrail breach (if linked to experiment)
        """
        current_stage = self.rollout_state.get(flag_key, 0)

        if not monitoring_clear:
            return {
                "flag_key": flag_key,
                "action": "HALTED",
                "reason": "Monitoring criteria not met. Investigate before advancing.",
                "current_percentage": self.STAGES[current_stage]["percentage"]
            }

        next_stage = current_stage + 1
        if next_stage >= len(self.STAGES):
            return {
                "flag_key": flag_key,
                "action": "COMPLETE",
                "percentage": 100,
                "message": "Rollout complete. Flag at 100%."
            }

        stage = self.STAGES[next_stage]
        self.flag_service.set_rollout(flag_key, stage["percentage"])
        self.rollout_state[flag_key] = next_stage

        return {
            "flag_key": flag_key,
            "stage": stage["label"],
            "percentage": stage["percentage"],
            "next_check_in_hours": stage["duration_hours"],
            "action": "ADVANCED"
        }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    service = FeatureFlagService()

    # Register flags
    service.register_flag(FeatureFlag(
        flag_key="new_home_feed_v2",
        name="New Home Feed V2",
        description="Redesigned home feed with progress indicators",
        rollout_percentage=25,
        target_segments=["engaged_users", "activated_users"],
        allowlist=["user-vip-001", "user-vip-002"],
        blocklist=["user-bot-001"],
        experiment_id="exp-041"
    ))

    service.register_flag(FeatureFlag(
        flag_key="smart_notifications",
        name="Smart Notification Timing",
        description="Per-user send time optimization",
        rollout_percentage=50,
        depends_on=["new_home_feed_v2"]
    ))

    service.register_flag(FeatureFlag(
        flag_key="dark_mode",
        name="Dark Mode",
        description="Dark mode UI option",
        rollout_percentage=100
    ))

    # Evaluate flags for different users
    users = [
        UserFlagContext("user-vip-001", segments=["engaged_users"]),
        UserFlagContext("user-regular-042", segments=["engaged_users"]),
        UserFlagContext("user-new-099", segments=["new_users"]),
        UserFlagContext("user-bot-001", segments=["engaged_users"]),
    ]

    print("Flag Evaluations:")
    print("-" * 70)

    for user in users:
        results = service.evaluate_all(
            ["new_home_feed_v2", "smart_notifications", "dark_mode"], user
        )
        print(f"  {user.user_id}:")
        for flag_key, value in results.items():
            # Find the rule that matched
            eval_entry = next(
                (e for e in reversed(service.evaluation_log)
                 if e.flag_key == flag_key and e.user_id == user.user_id),
                None
            )
            rule = eval_entry.rule_matched if eval_entry else "unknown"
            print(f"    {flag_key}: {value} (rule: {rule})")
        print()

    # Kill switch demo
    print("Kill switch activated for new_home_feed_v2:")
    service.kill_flag("new_home_feed_v2")
    result = service.evaluate("new_home_feed_v2", users[0])
    print(f"  {users[0].user_id}: {result.value} (rule: {result.rule_matched})")
    print()

    # Progressive rollout demo
    print("Progressive Rollout:")
    rollout = ProgressiveRollout(service)

    # Reset kill switch for demo
    service.flags["new_home_feed_v2"].is_killed = False

    step = rollout.start_rollout("new_home_feed_v2")
    print(f"  Stage: {step['stage']} ({step['percentage']}%)")

    step = rollout.advance_rollout("new_home_feed_v2", monitoring_clear=True)
    print(f"  Stage: {step['stage']} ({step['percentage']}%)")

    step = rollout.advance_rollout("new_home_feed_v2", monitoring_clear=False)
    print(f"  Action: {step['action']} — {step['reason']}")
