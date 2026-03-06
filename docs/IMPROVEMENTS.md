# Engagement & Personalization Engine -- Improvements & Roadmap

## Product Overview

The Engagement & Personalization Engine is a real-time platform for tracking, scoring, segmenting, and personalizing user engagement within a health and wellness application. It enables product and growth teams to:

- **Segment users in real-time** across four dimensions: lifecycle stage (new/activated/engaged/at-risk/dormant/reactivated), behavioral cohort (power/regular/casual/drifting/dormant/churned), engagement tier (1-5 scored 0-100), and goal cluster (weight management/fitness/mental wellness/chronic condition/general wellness).
- **Score engagement continuously** using a weighted composite model (recency 30%, frequency 25%, depth 20%, consistency 15%, progression 10%) that updates on every meaningful user event.
- **Generate personalized content recommendations** through a two-stage pipeline: candidate generation (cheap filters reducing a catalog to ~100 items) followed by ML-informed ranking (collaborative filtering 40%, content affinity 25%, freshness 15%, tier adjustment 10%, goal relevance 10%), with post-ranking diversity enforcement.
- **Run A/B experiments at scale** with deterministic hash-based assignment, sequential testing (O'Brien-Fleming spending function), guardrail monitoring with auto-stop, SRM detection, and segment decomposition for heterogeneous treatment effects.
- **Control feature rollouts** via a feature flag service with kill switches, progressive rollout stages (1% -> 5% -> 20% -> 50% -> 100%), segment targeting, allowlist/blocklist, and dependency chains.
- **Orchestrate notifications** through n8n workflows that trigger re-engagement campaigns when engagement scores drop below thresholds, respecting user notification preferences and optimal send times.

The system targets a health/wellness product vertical but the architecture is domain-agnostic and applicable to any SaaS engagement platform.

---

## Current Architecture

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Core API** | FastAPI 0.115.0, Uvicorn 0.30.0 | Event ingestion, scoring API, recommendation serving |
| **Data Validation** | Pydantic 2.10.0, Zod (TS) | Schema validation for events and models |
| **Primary Database** | PostgreSQL 16 (via Supabase) | User profiles, experiment config, feature flags, cohort assignments |
| **Real-time Cache** | Redis 7 | Segment membership, engagement scores, feature flag configs (<5ms p95) |
| **Event Streaming** | Apache Kafka (Confluent 7.5.0) | Event bus for raw events, scoring triggers, recommendation updates |
| **Data Warehouse** | Snowflake | Feature computation, historical analytics, ML training data |
| **Feature Store** | Feast 0.32.0 | Online (Redis) and offline (Snowflake) feature serving |
| **ML/Stats** | scikit-learn 1.3.2, scipy 1.11.4, statsmodels 0.14.0 | Scoring models, statistical tests, experiment analysis |
| **Background Jobs** | Trigger.dev | Nightly batch scoring, recommendation generation |
| **Workflow Orchestration** | n8n | Notification orchestration, cohort recalculation |
| **Analytics/Tracking** | PostHog, Segment CDP | Event tracking, feature flags, experiment assignment |
| **Email** | React Email, Resend | Weekly engagement digests, re-engagement campaigns |
| **Dashboard** | React + Recharts | 3-tab dashboard (engagement overview, experiments, recommendations) |
| **Monitoring** | Prometheus, Datadog, Sentry | Metrics, APM, error tracking |
| **Infrastructure** | Docker Compose, Vercel, ECS | Local dev, dashboard hosting, API deployment |

### Key Components

1. **`src/segmentation/user_segmenter.py`** -- Computes segment membership across four dimensions on every meaningful event. Caches results in Redis (TTL: 1 hour). Detects transitions and triggers interventions.

2. **`src/scoring/engagement_scorer.py`** -- Calculates a composite 0-100 engagement score from five weighted components. Uses stepped decay functions (not linear) for recency. Generates alerts for rapid decline, tier changes, approaching dormancy, and reactivation.

3. **`src/recommendations/recommendation_engine.py`** -- Two-stage recommendation pipeline with 55ms latency budget. Stage 1 filters to ~100 candidates; Stage 2 applies weighted ranking model. Includes diversity enforcement (max 2 same-category, max 3 same-type in top 10) and lifecycle-aware CTA selection.

4. **`src/experiments/experiment_framework.py`** -- Full A/B testing framework with SHA-256 deterministic assignment, O'Brien-Fleming sequential testing boundaries, SRM detection via chi-squared test, and guardrail monitoring with auto-stop at p < 0.01.

5. **`src/flags/feature_flags.py`** -- Feature flag service with 8-rule evaluation priority chain (kill switch > inactive > blocklist > allowlist > dependencies > segment targeting > rollout percentage > default). Includes progressive rollout manager with 5-stage deployment.

6. **`pipelines/feature_computation.sql`** -- Snowflake SQL pipeline computing engagement, churn risk, and recommendation features from raw Segment events. Runs daily via Snowflake Tasks.

7. **`pipelines/feast_features.py`** -- Feast feature definitions across four feature views (engagement, churn, recommendation, user profile) with online materialization to Redis every 6 hours.

8. **`trigger-jobs/engagement_scoring.ts`** -- Batch engagement scoring with checkpointing for large user bases. Processes users in batches of 100 with error isolation per batch.

9. **`trigger-jobs/recommendation_generation.ts`** -- Nightly recommendation generation using collaborative filtering + content-based hybrid approach with Thompson sampling for exploration/exploitation.

### Data Flow

```
User Action --> Segment CDP --> segment_receiver.py (FastAPI webhook)
    |
    +--> Kafka (events-raw topic)
    |       |
    |       +--> Snowflake (batch feature computation, daily 1am)
    |       |       |
    |       |       +--> Feast (materialize to Redis every 6h)
    |       |
    |       +--> Engagement Scorer (real-time via Kafka consumer)
    |               |
    |               +--> Redis (engagement:{user_id})
    |               +--> Segment transition detection
    |                       |
    |                       +--> n8n (notification orchestration)
    |
    +--> Recommendation Engine (nightly batch via Trigger.dev)
            |
            +--> Supabase (recommendations table)
            +--> Redis (pre-computed recs)
```

---

## Recommended Improvements

### 1. Replace Stepped Scoring Functions with Continuous Decay Curves

**Current state:** `engagement_scorer.py` uses discrete stepped functions for recency, frequency, depth, and consistency scoring (lines 222-322). For example, recency jumps from 80 to 65 at the 24-to-48 hour boundary, creating cliff effects where a user at 24.5 hours scores 15 points lower than one at 23.5 hours.

**Improvement:** Replace stepped functions with smooth continuous decay curves. Use exponential decay for recency (`score = 100 * exp(-lambda * hours)` with lambda calibrated to match current tier boundaries) and sigmoid curves for frequency and depth.

```python
import math

def compute_recency_continuous(self, hours_since: float) -> float:
    """Exponential decay: half-life of ~36 hours."""
    half_life = 36.0
    decay_rate = math.log(2) / half_life
    return 100.0 * math.exp(-decay_rate * hours_since)

def compute_frequency_continuous(self, sessions_per_week: float) -> float:
    """Sigmoid curve: midpoint at 3.5 sessions/week."""
    return 100.0 / (1.0 + math.exp(-1.5 * (sessions_per_week - 3.5)))
```

**Why:** Eliminates gaming incentives at boundaries and produces smoother segment transitions, reducing notification churn from rapid tier oscillation.

### 2. Add Vector Embedding-Based Collaborative Filtering

**Current state:** The recommendation engine in `recommendation_engine.py` uses a simple content affinity ratio (`category_count / total_interactions`, line 258) and relies on pre-computed collaborative filtering scores from SageMaker. The Trigger.dev job (`recommendation_generation.ts`, line 135-169) implements collaborative filtering as a simple SQL lookup of similar users by tier.

**Improvement:** Introduce vector embeddings for users and content items using a lightweight embedding model. Store embeddings in a vector database and compute similarity via approximate nearest neighbor search.

**Recommended stack:**
- **Qdrant** (https://github.com/qdrant/qdrant, v1.9+) -- Rust-based vector database with sub-10ms search latency, HNSW indexing, filtering, and payload support. Open source with managed cloud option.
- **sentence-transformers** (v3.0+) or a fine-tuned embedding model for encoding content metadata and user interaction histories into dense vectors.
- Alternative: **pgvector** (v0.7+) extension for PostgreSQL if staying within the existing Supabase stack. Supports IVFFlat and HNSW indexing, which is sufficient for catalogs under 100K items.

```python
# Example: pgvector integration for content embeddings
# In 001_initial_schema.sql:
# CREATE EXTENSION IF NOT EXISTS vector;
# ALTER TABLE content ADD COLUMN embedding vector(384);

# In recommendation_engine.py:
async def get_similar_content(self, content_id: str, top_k: int = 50):
    """ANN search for content similar to a given item."""
    result = await self.db.execute(
        "SELECT id, title, 1 - (embedding <=> $1) as similarity "
        "FROM content ORDER BY embedding <=> $1 LIMIT $2",
        [target_embedding, top_k]
    )
    return result
```

**Why:** The current affinity calculation is a single-dimensional category ratio. Vector embeddings capture multi-dimensional similarity (topic, difficulty, format, engagement pattern) and enable true collaborative filtering without requiring the full SageMaker inference pipeline.

### 3. Implement Real-Time Feature Computation with Streaming

**Current state:** Feature computation runs as a daily Snowflake batch job (`feature_computation.sql`) at 1am Pacific. Features can be up to 24 hours stale. Feast materialize runs every 6 hours. Combined worst-case staleness: ~30 hours.

**Improvement:** Add a streaming feature computation layer for latency-sensitive features (recency, session count, last action timestamp) while keeping batch computation for complex aggregates.

**Recommended approach:**
- **Bytewax** (https://github.com/bytewax/bytewax, v0.20+) -- Python-native stream processor built on Timely Dataflow. Supports stateful windowed aggregations with exactly-once semantics. Integrates natively with Kafka and Redis.
- Alternative: **Apache Flink** with PyFlink for heavier workloads, or **RisingWave** (https://github.com/risingwavelabs/risingwave, v1.9+) as a streaming database that speaks PostgreSQL wire protocol.

```python
# bytewax streaming feature pipeline
from bytewax.dataflow import Dataflow
from bytewax.connectors.kafka import KafkaInput
from bytewax.window import TumblingWindow, SystemClockConfig

flow = Dataflow("engagement-features")
flow.input("events", KafkaInput(brokers=["kafka:9092"], topics=["events-raw"]))
flow.map(parse_event)
flow.key_by(lambda e: e.user_id)
flow.fold_window(
    "session_count",
    SystemClockConfig(),
    TumblingWindow(length=timedelta(hours=1)),
    builder=lambda: 0,
    folder=lambda count, event: count + 1,
)
flow.output("redis", RedisOutput(host="redis", port=6379))
```

**Why:** Real-time features enable immediate score updates after user actions. Currently, a user who completes a key action must wait up to 24+ hours for their engagement score to reflect it, missing the intervention window for at-risk users.

### 4. Add Multi-Armed Bandit for CTA Optimization

**Current state:** CTA selection in `recommendation_engine.py` (lines 394-449) uses a static mapping from lifecycle stage to CTA template. Every user in the same lifecycle stage sees the same CTA, with no learning or optimization.

**Improvement:** Implement a contextual multi-armed bandit (CMAB) for CTA selection that learns which CTA variants perform best for different user contexts.

**Recommended library:**
- **Vowpal Wabbit** (https://github.com/VowpalWabbit/vowpal_wabbit, v9.10+) -- Production-grade contextual bandit with low latency inference. Supports cost-sensitive classification and action-dependent features.
- Lighter alternative: implement Thompson Sampling (already partially present in `recommendation_generation.ts`, line 118-128) with a Beta-Bernoulli model per CTA-segment pair, storing alpha/beta parameters in Redis.

```python
class CTABandit:
    """Thompson Sampling bandit for CTA optimization."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def select_cta(self, user_context: dict, cta_options: list) -> dict:
        segment_key = f"{user_context['lifecycle_stage']}:{user_context['engagement_tier']}"
        best_score = -1
        best_cta = cta_options[0]

        for cta in cta_options:
            key = f"bandit:cta:{segment_key}:{cta['action']}"
            alpha = float(await self.redis.hget(key, "alpha") or 1)
            beta = float(await self.redis.hget(key, "beta") or 1)
            score = random.betavariate(alpha, beta)
            if score > best_score:
                best_score = score
                best_cta = cta

        return best_cta

    async def update(self, segment_key: str, cta_action: str, reward: float):
        key = f"bandit:cta:{segment_key}:{cta_action}"
        if reward > 0:
            await self.redis.hincrby(key, "alpha", 1)
        else:
            await self.redis.hincrby(key, "beta", 1)
```

**Why:** Static CTA mappings leave substantial engagement uplift on the table. Bandits converge quickly (typically within 1,000-2,000 impressions per arm per segment) and naturally handle non-stationarity as user preferences shift.

### 5. Implement Proper Exposure Logging and Intent-to-Treat Analysis

**Current state:** The experiment framework (`experiment_framework.py`) has an `ExposureEvent` dataclass (line 119-125) but the assignment engine returns assignments without logging whether the user actually saw the variant. The Trigger.dev scoring job (`engagement_scoring.ts`, line 307) logs transitions but does not track exposure.

**Improvement:** Implement client-side exposure logging that fires when the user actually renders the variant (not just when assigned). This enables intent-to-treat (ITT) analysis alongside as-treated analysis, which is critical for valid causal inference.

```python
# Add to experiment_framework.py
class ExposureTracker:
    """Track actual exposure (rendering) vs. assignment."""

    def __init__(self, redis_client, kafka_producer):
        self.redis = redis_client
        self.kafka = kafka_producer

    async def log_exposure(self, user_id: str, experiment_id: str,
                           variant_id: str, surface: str):
        """Called from client when variant is rendered."""
        exposure_key = f"exposure:{experiment_id}:{user_id}"

        # Deduplicate: only log first exposure per user per experiment
        if await self.redis.exists(exposure_key):
            return

        await self.redis.set(exposure_key, variant_id, ex=86400 * 30)

        event = ExposureEvent(
            user_id=user_id,
            experiment_id=experiment_id,
            variant_id=variant_id,
            surface=surface,
        )
        await self.kafka.send("experiment-exposures", event.__dict__)
```

**Why:** Without exposure logging, assignment-based analysis inflates the denominator with users who were assigned but never saw the treatment, diluting the measured effect. This is a known source of Type II errors in experimentation platforms.

### 6. Add Feature Flag Lifecycle Automation

**Current state:** `feature_flags.py` has a `get_stale_flags()` method (line 361-386) that identifies flags unchanged for 30+ days, but the cleanup is manual.

**Improvement:** Automate flag lifecycle management with scheduled cleanup alerts, auto-archival of flags at 100% rollout for 14+ days, and integration with the CI/CD pipeline to detect dead flag references in code.

**Recommended tool:**
- **Unleash** (https://github.com/Unleash/unleash, v6.0+) -- Open-source feature flag platform with built-in stale flag detection, flag lifecycle tracking, and SDK support for gradual rollouts. Alternatively, enhance the existing PostHog feature flag integration which already supports flag lifecycle management.

### 7. Replace Zookeeper-Dependent Kafka with KRaft or Redpanda

**Current state:** `docker-compose.yml` runs Confluent Kafka 7.5.0 with a separate Zookeeper container (lines 64-99). This adds operational overhead and a single point of failure.

**Improvement:**
- **Option A:** Upgrade to Kafka 3.7+ with KRaft mode (no Zookeeper). KRaft has been production-ready since Kafka 3.3 and is the default in 3.7+.
- **Option B:** Replace with **Redpanda** (https://github.com/redpanda-data/redpanda, v24.1+) -- a Kafka API-compatible streaming platform written in C++ with no Zookeeper dependency, lower tail latency (p99 < 10ms vs Kafka's ~50ms), and 10x lower resource usage. Drop-in replacement for Kafka clients.

```yaml
# docker-compose.yml -- Redpanda replaces Kafka + Zookeeper
services:
  redpanda:
    image: docker.redpanda.com/redpandadata/redpanda:v24.1.1
    container_name: engagement-redpanda
    command:
      - redpanda start
      - --smp 1
      - --memory 1G
      - --kafka-addr internal://0.0.0.0:29092,external://0.0.0.0:9092
      - --advertise-kafka-addr internal://redpanda:29092,external://localhost:9092
    ports:
      - "9092:9092"
      - "29092:29092"
      - "8081:8081"  # Schema registry
```

**Why:** Eliminates the Zookeeper container, reduces Docker Compose complexity, and cuts memory usage for local development. The existing `confluent-kafka` Python client works unchanged against Redpanda.

### 8. Add Comprehensive Unit and Integration Tests

**Current state:** `requirements.txt` includes pytest 8.3.0 and pytest-asyncio 0.24.0 but there are no test files in the project. All source files have `if __name__ == "__main__"` demo blocks but no formal test suite.

**Improvement:** Add structured tests covering:
- Segmentation boundary conditions and transition detection
- Scoring component accuracy and weight calibration
- Experiment assignment uniformity (statistical test over 100K synthetic IDs)
- Feature flag evaluation rule priority
- Recommendation diversity enforcement constraints
- API endpoint validation and error handling

```
tests/
  test_segmentation.py      # Lifecycle transitions, cohort boundaries
  test_scoring.py            # Component scores, composite calculation, alerts
  test_recommendations.py    # Candidate filtering, ranking, diversity
  test_experiments.py        # Assignment uniformity, SRM detection, sequential
  test_feature_flags.py      # Rule priority, kill switch, progressive rollout
  test_segment_receiver.py   # API endpoints, validation, error cases
  conftest.py                # Shared fixtures (Redis mock, Supabase mock)
```

### 9. Implement Score Weight Auto-Tuning

**Current state:** Engagement score weights (`SCORE_WEIGHTS` in `engagement_scorer.py`, line 34-39) and recommendation ranking weights (`RANKING_WEIGHTS` in `recommendation_engine.py`, line 92-98) are manually calibrated constants.

**Improvement:** Implement periodic weight optimization using Bayesian optimization or gradient-free search to maximize a target metric (e.g., 30-day retention correlation).

**Recommended library:**
- **Optuna** (https://github.com/optuna/optuna, v3.6+) -- Hyperparameter optimization framework with TPE sampler, pruning, and dashboard. Run weekly over historical data to suggest weight adjustments.

```python
import optuna

def objective(trial):
    weights = {
        "recency": trial.suggest_float("recency", 0.15, 0.45),
        "frequency": trial.suggest_float("frequency", 0.10, 0.40),
        "depth": trial.suggest_float("depth", 0.05, 0.35),
        "consistency": trial.suggest_float("consistency", 0.05, 0.25),
        "progression": trial.suggest_float("progression", 0.05, 0.20),
    }
    # Normalize weights to sum to 1.0
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    # Score all historical users with these weights
    scorer = EngagementScorer(weights=weights)
    # ... compute scores and correlate with actual 30-day retention
    return correlation_with_retention

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=200)
```

### 10. Add Rate Limiting and Backpressure to Event Ingestion

**Current state:** `segment_receiver.py` has commented-out rate limiting code (lines 147-149) and no backpressure mechanism when Kafka is slow or unavailable.

**Improvement:** Implement proper rate limiting per user and global circuit breaking for downstream services.

**Recommended approach:**
- Use **Redis-based sliding window rate limiting** (token bucket or sliding window log) with `redis` library's built-in Lua scripting support.
- Add **circuit breakers** via `tenacity` (https://github.com/jd/tenacity, v8.2+) for Kafka producer calls with exponential backoff.
- Implement a **dead-letter queue** for events that fail validation or downstream processing.

---

## New Technologies & Trends

### 1. LLM-Powered Personalization

Large language models are increasingly used in personalization engines for:
- **Natural language content understanding:** Encode content descriptions and user interactions into semantic embeddings for richer similarity matching, replacing hand-crafted category labels.
- **Explanation generation:** Generate human-readable explanations for why content was recommended (e.g., "Because you completed 5 meditation sessions this week and users like you also enjoyed breathing exercises").
- **Dynamic CTA copy generation:** Instead of static CTA templates (current approach in `recommendation_engine.py` lines 402-433), use an LLM to generate personalized CTA copy that references the user's specific goals and recent activity.

**Relevant tools:**
- **OpenAI Embeddings API** (text-embedding-3-small) -- $0.02/1M tokens, 1536-dimensional embeddings ideal for content similarity.
- **Cohere Embed v3** -- Optimized for search and retrieval, supports 1024-dimensional embeddings with compression.
- **LiteLLM** (https://github.com/BerriAI/litellm, v1.40+) -- Unified interface for 100+ LLM providers with rate limiting, caching, and fallbacks. Useful for abstracting the embedding provider.

**Application to this project:** Replace the manual `goal_to_cluster` mapping in `user_segmenter.py` (lines 282-297) and `category_to_cluster` mapping (lines 306-316) with semantic similarity between user goal descriptions and cluster definitions. This eliminates the need to manually maintain mapping dictionaries as new content categories are added.

### 2. Real-Time ML Inference at the Edge

The trend toward sub-10ms personalization decisions requires moving inference closer to the user:
- **ONNX Runtime** (https://github.com/microsoft/onnxruntime, v1.18+) -- Run scoring models exported to ONNX format directly in the API process, eliminating the SageMaker network hop. Supports Python, Node.js, and Rust runtimes.
- **Wasm-based inference** with **Tract** (https://github.com/sonos/tract) for ultra-low-latency model execution in edge workers.
- **Feature pre-computation and caching** with Redis Streams and consumer groups for fan-out to multiple scoring services.

**Application to this project:** The current 55ms latency budget for recommendations (`recommendation_engine.py` line 18) could be reduced to <15ms by running the ranking model locally via ONNX Runtime instead of calling SageMaker. The model is small enough (5 weighted components) to run in-process.

### 3. Causal Inference Beyond A/B Testing

Modern experimentation platforms are moving beyond simple A/B tests:
- **CUPED (Controlled-experiment Using Pre-Experiment Data)** -- Variance reduction technique that uses pre-experiment metric values as covariates, reducing required sample sizes by 30-50%. Implemented in `statsmodels` via OLS regression with pre-period control variables.
- **Synthetic control methods** -- For experiments where randomization is infeasible (e.g., geographic rollouts), use the `CausalImpact` library (https://github.com/google/CausalImpact) or `SyntheticControlMethods` Python package.
- **Double ML / Causal Forests** via **EconML** (https://github.com/py-why/EconML, v0.15+) -- Estimate heterogeneous treatment effects across user segments, enabling targeted rollout decisions (ship for segment A, iterate for segment B).
- **GrowthBook** (https://github.com/growthbook/growthbook, v3.0+) -- Open-source experimentation platform with built-in CUPED, Bayesian analysis, and feature flag integration. Could replace the custom experiment framework.

**Application to this project:** The experiment framework (`experiment_framework.py`) currently uses a basic z-test for proportions (line 282-342). Adding CUPED would significantly reduce the time-to-decision for the 50+ experiments run per quarter. The `segment decomposition for heterogeneous treatment effects` mentioned in the module docstring is not implemented -- EconML's CausalForest would fill this gap.

### 4. Privacy-Preserving Personalization

With GDPR, CCPA, and the deprecation of third-party cookies, privacy-preserving techniques are becoming essential:
- **Differential privacy** for aggregate feature computation -- add calibrated noise to feature store queries to prevent individual re-identification. Libraries: **Google's differential-privacy** (https://github.com/google/differential-privacy) or **OpenDP** (https://github.com/opendp/opendp, v0.10+).
- **On-device personalization** -- Run lightweight scoring models on the client device using ONNX or TensorFlow Lite, so raw user data never leaves the device.
- **Federated learning** -- Train recommendation models across user devices without centralizing raw data. Framework: **Flower** (https://github.com/adap/flower, v1.8+).

### 5. Feature Store Evolution

The feature store landscape has matured significantly:
- **Tecton** (https://tecton.ai) -- Managed feature platform with real-time feature computation (sub-second), automated feature monitoring, and native Snowflake integration. Eliminates the gap between Feast's batch materialization and real-time needs.
- **Chalk** (https://chalk.ai) -- Developer-first feature store with Python-native feature definitions, streaming + batch computation, and built-in data quality monitoring. Strong fit for teams already using Python-heavy stacks.
- **Hopsworks** (https://github.com/logicalclocks/hopsworks, v3.7+) -- Open-source feature store with Kafka-based streaming feature pipelines, built-in model registry, and support for complex feature transformations.

**Application to this project:** Feast 0.32.0 (current version) requires manual materialization scheduling and has limited real-time computation support. The 6-hour materialization cycle (`feast_features.py` comment, line 328) means features can be significantly stale. Upgrading to Feast 0.40+ (which adds push-based features and improved streaming support) or migrating to Tecton/Chalk would close the real-time gap.

### 6. Notification Intelligence

Modern notification systems go beyond rule-based triggers:
- **Send-time optimization (STO)** -- Learn optimal notification delivery times per user using a Gaussian process model over historical open-time distributions. Library: **GPyTorch** (https://github.com/cornellius-gp/gpytorch, v1.11+).
- **Notification fatigue modeling** -- Predict the marginal value of each notification and suppress low-value notifications. The current system tracks `notification_dismissed` and `notification_opt_out` events (in `segment_receiver.py`, line 64-77) but does not use them for send-rate throttling.
- **Channel optimization** -- Select the best channel (email, push, in-app, SMS) per user per message type using a multi-channel bandit.

**Relevant tool:** **OneSignal** (https://onesignal.com) or **Customer.io** (https://customer.io) for managed intelligent notification delivery with built-in STO and fatigue management.

### 7. Observability for ML Systems

Production ML systems require specialized observability beyond traditional APM:
- **Evidently AI** (https://github.com/evidentlyai/evidently, v0.4.30+) -- Open-source ML monitoring for data drift detection, prediction quality tracking, and feature importance monitoring. Generates dashboards and alerts when model input distributions shift.
- **Whylogs** (https://github.com/whylabs/whylogs, v1.3+) -- Lightweight data logging for feature distributions with statistical profiling and drift detection. Integrates with Feast.
- **Arize AI** (https://arize.com) -- Managed ML observability platform with embedding drift detection, prediction explainability, and automatic root cause analysis.

**Application to this project:** The feature quality checks in `feature_computation.sql` (Section 8, lines 306-332) compute basic statistics (min, max, mean, stddev) but do not detect distribution drift or correlate feature changes with model performance changes. Evidently AI would provide automated drift alerts when user behavior patterns shift (e.g., seasonal changes in wellness engagement).

### 8. Modern Dashboard Frameworks

The current React + Recharts dashboard (`dashboard.jsx`) uses hardcoded synthetic data. For production:
- **Tremor** (https://github.com/tremorlabs/tremor, v3.17+) -- React component library specifically designed for dashboards and data visualization, with built-in dark mode, responsive charts, and accessibility.
- **Evidence** (https://github.com/evidence-dev/evidence, v30+) -- Markdown-based BI tool that generates interactive dashboards from SQL queries. Ideal for the analytics-heavy experiment and cohort views.
- **Apache Superset** (https://github.com/apache/superset, v4.0+) -- Open-source BI platform with rich SQL IDE, 40+ visualization types, and native Snowflake connector. Could replace the custom React dashboard with a zero-code solution.

---

## Priority Roadmap

### P0 -- Critical (Weeks 1-4)

| # | Improvement | Effort | Impact | Dependencies |
|---|------------|--------|--------|-------------|
| 1 | **Add unit and integration test suite** | 2 weeks | High -- validates all scoring, segmentation, and assignment logic; enables safe refactoring | pytest, pytest-asyncio |
| 2 | **Implement exposure logging for experiments** | 1 week | High -- fixes fundamental measurement gap in experiment analysis | Redis, Kafka |
| 3 | **Add rate limiting and backpressure to event ingestion** | 1 week | High -- prevents cascading failures under load; currently has zero protection | Redis, tenacity |
| 4 | **Replace Zookeeper Kafka with KRaft mode or Redpanda** | 3 days | Medium -- reduces local dev complexity and operational overhead | Docker Compose update |

### P1 -- High Value (Weeks 5-10)

| # | Improvement | Effort | Impact | Dependencies |
|---|------------|--------|--------|-------------|
| 5 | **Implement real-time streaming features with Bytewax** | 3 weeks | High -- reduces feature staleness from 24h to <1 minute for critical signals | Bytewax, Kafka, Redis |
| 6 | **Replace stepped scoring with continuous decay curves** | 1 week | Medium -- smoother transitions, fewer false-positive tier changes | None (pure Python refactor) |
| 7 | **Add CUPED variance reduction to experiment framework** | 1 week | High -- 30-50% faster experiment decisions across 50+ quarterly experiments | statsmodels |
| 8 | **Implement contextual bandit for CTA optimization** | 2 weeks | Medium-High -- learns optimal CTAs per segment automatically | Redis, VW or custom Thompson Sampling |

### P2 -- Strategic (Weeks 11-20)

| # | Improvement | Effort | Impact | Dependencies |
|---|------------|--------|--------|-------------|
| 9 | **Add vector embeddings for recommendations (pgvector)** | 3 weeks | High -- transforms recommendation quality with semantic understanding | pgvector, embedding model |
| 10 | **Implement score weight auto-tuning with Optuna** | 2 weeks | Medium -- automated calibration of engagement and ranking weights | Optuna, historical data |
| 11 | **Add ML observability with Evidently AI** | 1 week | Medium -- automated drift detection and feature quality monitoring | Evidently, Grafana |
| 12 | **Upgrade Feast to 0.40+ or evaluate Tecton/Chalk** | 2 weeks | Medium -- better real-time feature support, reduced materialization lag | Feast upgrade or migration |
| 13 | **Migrate dashboard to Tremor or Evidence** | 2 weeks | Medium -- replace synthetic data with live queries, add interactivity | Tremor/Evidence, Snowflake |

### P3 -- Future (Weeks 20+)

| # | Improvement | Effort | Impact | Dependencies |
|---|------------|--------|--------|-------------|
| 14 | **LLM-powered content understanding and CTA generation** | 4 weeks | Medium-High -- eliminates manual category mappings, dynamic personalization | LiteLLM, embedding API |
| 15 | **Heterogeneous treatment effect estimation with EconML** | 3 weeks | Medium -- enables segment-specific ship/iterate/kill decisions | EconML, experiment data |
| 16 | **Notification intelligence (STO + fatigue modeling)** | 4 weeks | Medium -- optimizes delivery timing and reduces notification fatigue | GPyTorch or Customer.io |
| 17 | **Privacy-preserving features (differential privacy)** | 3 weeks | Low-Medium -- regulatory compliance, competitive differentiator | OpenDP |
| 18 | **ONNX Runtime for in-process scoring inference** | 2 weeks | Low-Medium -- reduces recommendation latency from 55ms to <15ms | ONNX Runtime |
| 19 | **Feature flag lifecycle automation** | 1 week | Low -- automates stale flag cleanup, reduces technical debt | Unleash or PostHog enhancement |
| 20 | **Replace GrowthBook or custom experimentation with Eppo/Statsig** | 4 weeks | Medium -- managed experimentation with warehouse-native analysis | Evaluation phase needed |

---

### Summary of Key Technology Recommendations

| Category | Current | Recommended | Rationale |
|----------|---------|-------------|-----------|
| Event Streaming | Kafka + Zookeeper | Kafka KRaft or Redpanda | Eliminate Zookeeper dependency |
| Feature Store | Feast 0.32.0 | Feast 0.40+ or Tecton/Chalk | Real-time feature support |
| Vector Search | None | pgvector or Qdrant | Embedding-based recommendations |
| Stream Processing | None (batch only) | Bytewax or RisingWave | Real-time feature computation |
| Experiment Analysis | Custom z-test | + CUPED + EconML | Faster decisions, HTE estimation |
| ML Observability | Basic SQL stats | Evidently AI + Whylogs | Automated drift detection |
| Weight Optimization | Manual constants | Optuna | Automated calibration |
| CTA Selection | Static lifecycle mapping | Contextual bandit (VW/Thompson) | Adaptive optimization |
| Dashboard | React + Recharts (synthetic) | Tremor or Evidence | Live data, better DX |
| Notifications | n8n rule-based | + STO + fatigue modeling | Intelligent delivery |
