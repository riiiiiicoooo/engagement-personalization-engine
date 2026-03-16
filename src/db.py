"""
Database connection pooling and persistence layer for engagement engine.

Provides SQLAlchemy with QueuePool connection management and ORM models
for persisting experiment assignments and user segments (ML outputs).

Design:
- QueuePool for efficient connection management (pool_size=10, max_overflow=20)
- SQLAlchemy ORM for type-safe queries and transactions
- Redis cache layer for hot data (segments with 1-hour TTL)
- Fallback to database for historical data and reproducibility

Models:
- UserSegmentHistory: tracks segment assignments per user with timestamps
- ExperimentAssignment: persists experiment variant assignments for analysis
"""

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    JSON,
    Index,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/engagement_engine"
)

# Connection pool configuration
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # 1 hour
POOL_PRE_PING = True  # Verify connections are alive before using

# Create engine with QueuePool
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,
    echo=False,  # Set True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Declarative base for ORM models
Base = declarative_base()


# ============================================================================
# ORM Models
# ============================================================================


class UserSegmentHistory(Base):
    """
    Persistent storage of user segment assignments.

    Each time a user's segments are computed, a new record is inserted.
    This enables:
    - Segment transition tracking and analytics
    - Reproducibility: recompute user's state at any point in time
    - Debugging: compare computed vs. cached segments
    - ML feedback loops: ground truth for segment quality
    """

    __tablename__ = "user_segment_history"

    # Primary key and user reference
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)

    # Segment dimensions (from SegmentMembership dataclass)
    lifecycle_stage = Column(String(50), nullable=False)
    behavioral_cohort = Column(String(50), nullable=False)
    engagement_tier = Column(Integer, nullable=False)
    goal_cluster = Column(String(10), nullable=False)
    custom_segments = Column(JSON, default=list)  # list of custom segment names

    # Metadata
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_user_segment_user_id_created", "user_id", "created_at"),
        Index("ix_user_segment_lifecycle_stage", "lifecycle_stage"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserSegmentHistory(user_id={self.user_id}, "
            f"lifecycle={self.lifecycle_stage}, tier={self.engagement_tier}, "
            f"computed_at={self.computed_at})>"
        )


class ExperimentAssignment(Base):
    """
    Persistent storage of experiment variant assignments.

    Each experiment assignment is immutable (write-once) to maintain
    consistency for analysis and reproducibility.

    Enables:
    - Experiment impact analysis: compare outcomes by variant
    - Variant persistence: user stays in same variant across sessions
    - Audit trail: every assignment is timestamped with context
    - ML training: ground truth labels for variant outcomes
    """

    __tablename__ = "experiment_assignments"

    # Primary key
    id = Column(Integer, primary_key=True)

    # Experiment and user reference
    user_id = Column(String(255), nullable=False, index=True)
    experiment_id = Column(String(255), nullable=False)

    # Assignment outcome
    variant = Column(String(100), nullable=False)  # e.g., "control", "treatment_a", "treatment_b"
    assignment_reason = Column(String(255))  # e.g., "random", "targeted", "holdout"

    # Context at assignment time (for analysis)
    lifecycle_stage = Column(String(50))  # User's stage when assigned
    engagement_tier = Column(Integer)  # User's tier when assigned
    context = Column(JSON)  # Additional context (goals, cohorts, custom segments)

    # Timing
    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_experiment_assignment_user_experiment", "user_id", "experiment_id"),
        Index("ix_experiment_assignment_variant", "variant"),
        Index("ix_experiment_assignment_assigned_at", "assigned_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExperimentAssignment(experiment={self.experiment_id}, "
            f"user={self.user_id}, variant={self.variant}, "
            f"assigned_at={self.assigned_at})>"
        )


# ============================================================================
# Database Utilities
# ============================================================================


def init_db() -> None:
    """Initialize database schema. Call once on startup."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Get a database session. Use as context manager or with cleanup."""
    return SessionLocal()


def close_db() -> None:
    """Close all connections in the pool. Call on shutdown."""
    engine.dispose()


def save_user_segment(
    user_id: str,
    lifecycle_stage: str,
    behavioral_cohort: str,
    engagement_tier: int,
    goal_cluster: str,
    custom_segments: Optional[list] = None,
    computed_at: Optional[datetime] = None,
) -> UserSegmentHistory:
    """
    Persist a user's computed segment assignment.

    This should be called after computing segments in UserSegmenter.compute_segments()
    to ensure reproducibility and enable transition tracking.

    Args:
        user_id: User identifier
        lifecycle_stage: From LifecycleStage enum
        behavioral_cohort: From BehavioralCohort enum
        engagement_tier: 1-5 integer
        goal_cluster: From GoalCluster enum (A-E)
        custom_segments: List of custom segment names
        computed_at: When the segment was computed (default: now)

    Returns:
        Persisted UserSegmentHistory record
    """
    if computed_at is None:
        computed_at = datetime.utcnow()

    session = get_session()
    try:
        record = UserSegmentHistory(
            user_id=user_id,
            lifecycle_stage=lifecycle_stage,
            behavioral_cohort=behavioral_cohort,
            engagement_tier=engagement_tier,
            goal_cluster=goal_cluster,
            custom_segments=custom_segments or [],
            computed_at=computed_at,
        )
        session.add(record)
        session.commit()
        return record
    finally:
        session.close()


def save_experiment_assignment(
    user_id: str,
    experiment_id: str,
    variant: str,
    assignment_reason: Optional[str] = None,
    lifecycle_stage: Optional[str] = None,
    engagement_tier: Optional[int] = None,
    context: Optional[dict] = None,
) -> ExperimentAssignment:
    """
    Persist an experiment assignment for a user.

    This is write-once: the same user-experiment pair should only be assigned once.
    Subsequent requests for the same pair should retrieve from database/cache.

    Args:
        user_id: User identifier
        experiment_id: Experiment identifier
        variant: The assigned variant (e.g., "control", "treatment_a")
        assignment_reason: How the variant was chosen
        lifecycle_stage: User's segment stage at assignment time
        engagement_tier: User's tier at assignment time
        context: Additional context (goal_cluster, cohort, etc.)

    Returns:
        Persisted ExperimentAssignment record
    """
    session = get_session()
    try:
        record = ExperimentAssignment(
            user_id=user_id,
            experiment_id=experiment_id,
            variant=variant,
            assignment_reason=assignment_reason,
            lifecycle_stage=lifecycle_stage,
            engagement_tier=engagement_tier,
            context=context or {},
        )
        session.add(record)
        session.commit()
        return record
    finally:
        session.close()


def get_user_segment_history(
    user_id: str, limit: int = 10
) -> list[UserSegmentHistory]:
    """
    Retrieve recent segment assignments for a user.

    Args:
        user_id: User identifier
        limit: Maximum number of records to return (default: 10)

    Returns:
        List of UserSegmentHistory records, most recent first
    """
    session = get_session()
    try:
        return (
            session.query(UserSegmentHistory)
            .filter(UserSegmentHistory.user_id == user_id)
            .order_by(UserSegmentHistory.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        session.close()


def get_experiment_assignment(
    user_id: str, experiment_id: str
) -> Optional[ExperimentAssignment]:
    """
    Retrieve a user's assignment for a specific experiment.

    Returns None if user has not been assigned to this experiment.

    Args:
        user_id: User identifier
        experiment_id: Experiment identifier

    Returns:
        ExperimentAssignment record or None
    """
    session = get_session()
    try:
        return (
            session.query(ExperimentAssignment)
            .filter(
                ExperimentAssignment.user_id == user_id,
                ExperimentAssignment.experiment_id == experiment_id,
            )
            .first()
        )
    finally:
        session.close()


# ============================================================================
# Connection Pool Lifecycle
# ============================================================================


@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Hook: executed when a new database connection is created."""
    # Example: set connection parameters for PostgreSQL
    cursor = dbapi_conn.cursor()
    cursor.execute("SET SESSION search_path = public")
    cursor.close()


if __name__ == "__main__":
    # Example: initialize database and create tables
    init_db()
    print("Database initialized successfully")
