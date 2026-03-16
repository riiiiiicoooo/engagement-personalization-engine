# Engagement Personalization Engine — Capacity Plan

**Last Updated:** March 2026
**Baseline Workload:** 200K daily active users, 1M recommendations/day, 50 concurrent A/B tests

---

## Current State (200K DAU, 1M recommendations/day)

### Infrastructure

| Component | Current | Headroom | Notes |
|-----------|---------|----------|-------|
| **API servers (FastAPI)** | 4 x t3.large (2 CPU, 8GB) | 45% CPU avg | Peak hours (6-10pm) hit 70% |
| **Kafka (events + experiment assignments)** | 3-broker cluster (m5.large each) | 50% disk utilization | Topic partitions: 100 (10 per user bucket) |
| **Feature store (in-memory)** | 2 x r6g.2xlarge (8 CPU, 64GB) | 55% memory | ~50K hot user profiles cached |
| **ML model serving (TensorFlow Lite)** | On-device (mobile app cache) + 2 backend serving instances (t3.2xlarge) | 40% CPU | 95% on-device; 5% fallback to backend |
| **Spark (batch feature engineering)** | 8-node cluster (m5.xlarge) | 50% utilization | Daily jobs: feature generation + model retraining |
| **PostgreSQL (experiments, user cohorts)** | 1 x r6g.xlarge (4 CPU, 32GB) | 40% storage, 50% CPU | Experiment metadata + cohort definitions |

### Cost

| Category | Monthly | Annual |
|----------|---------|--------|
| API servers (EC2) | $2.4K | $29K |
| Kafka cluster | $2.1K | $25K |
| Feature store (Redis) | $1.8K | $22K |
| ML model serving | $1.5K | $18K |
| Spark cluster | $2.8K | $34K |
| Database (RDS) | $0.8K | $10K |
| Storage (S3 event logs) | $0.6K | $7K |
| **Total** | **$12.0K** | **$145K** |

### Performance Baseline

| Metric | Value | SLO |
|--------|-------|-----|
| Recommendation latency (p95) | 88ms | 150ms ✓ |
| NDCG@10 (recommendation quality) | 0.72 | 0.72 ✓ |
| Churn prediction AUC | 0.84 | 0.84 ✓ |
| Feature freshness (p95) | 3.2 min | 10 min ✓ |
| Experiment SRM rate | 0% | 0% ✓ |
| Kafka message ordering | 99.95% | 99.9% ✓ |

### What Breaks First at Current Load

1. **Kafka disk capacity** — 1M recommendations/day * 3 retention = 3M messages stored; at peak hours, disk I/O to Kafka hits 80%
2. **Feature store memory** — 200K DAU * 50KB per user profile = 10GB; currently caching 50K hot profiles (hot/active users only); cold user lookups cause cache misses
3. **Spark batch jobs** — Daily model retraining takes 4 hours; if job runs during peak recommendation hours, feature pipeline latency exceeds 10 min SLO
4. **PostgreSQL experiment table** — 50 concurrent A/B tests means experiment metadata (variant assignments, user cohorts) becomes hot; query latency hits 200ms during assignment lookups

---

## 2x Scenario (400K DAU, 2M recommendations/day)

### What Changes

- **User growth:** Subscriber base doubles (viral growth, new markets)
- **Test velocity:** More experiments running concurrently (100+ tests)
- **Feature complexity:** More personalization signals (social influence, seasonal, trending)
- **Batch job complexity:** Model training complexity increases; job duration grows

### Infrastructure Changes

| Component | 1x → 2x | Action | Timeline |
|-----------|---------|--------|----------|
| **API servers** | 4 → 8 instances (t3.large) | Horizontal scale; enable autoscaling | Week 1 |
| **Kafka** | 3 brokers → 5 brokers | Increase capacity; add partitions (200 vs. 100) | Month 1 |
| **Feature store** | 2 x r6g.2xlarge → 4 x r6g.2xlarge | Double size; implement LRU eviction for cold users | Month 1 |
| **ML serving** | 2 backend instances → 4 instances | Increase fallback capacity (on-device still 95%) | Month 1 |
| **Spark cluster** | 8 nodes → 15 nodes | Increase parallelism; reduce job duration from 4h to 2h | Month 2 |
| **PostgreSQL** | Single primary → Primary + 2 read replicas | Experiment metadata queries → read replicas | Month 1 |

### Cost Impact

| Category | 1x | 2x | Delta | % increase |
|----------|----|----|-------|-----------|
| Compute (API servers) | $2.4K | $4.2K | +$1.8K | +75% |
| Kafka | $2.1K | $4.2K | +$2.1K | +100% |
| Feature store | $1.8K | $3.2K | +$1.4K | +78% |
| ML serving | $1.5K | $2.8K | +$1.3K | +87% |
| Spark | $2.8K | $5.2K | +$2.4K | +86% |
| Database | $0.8K | $1.5K | +$0.7K | +88% |
| Storage | $0.6K | $1.2K | +$0.6K | +100% |
| **Total** | **$12.0K** | **$22.3K** | **+$10.3K** | **+86%** |

### Performance at 2x

| Metric | 1x Baseline | 2x Expected | Status |
|--------|------------|-------------|--------|
| Recommendation latency (p95) | 88ms | 115ms | Still within SLO ✓ |
| Feature freshness (p95) | 3.2min | 4.5min | Still within SLO ✓ |
| NDCG@10 | 0.72 | 0.71 | Slight degradation (more users = less personalized); acceptable |
| Kafka ordering violations | 0% | <0.1% | Acceptable |

### What Breaks First at 2x

1. **Feature store hot-user cache hit rate drops** — More diverse user population means cache hit rate drops from 80% to 60%; cold user lookups increase latency
2. **Spark job duration exceeds optimal window** — Even with 15 nodes, training complexity grows faster than compute; job duration hits 3-4 hours; overlaps with peak recommendation window
3. **Kafka partition rebalancing** — With 200 partitions and 5 brokers, rebalancing becomes frequent and slow; message ordering violations increase
4. **PostgreSQL query performance** — Experiment metadata queries slow under 100 concurrent tests; need to shard experiment table

### Scaling Triggers for 2x

- **Feature cache hit rate < 60%:** Upgrade to larger instance (r6g.3xlarge) or implement tiered caching (Memcached for L1)
- **Spark job duration > 3 hours:** Parallelize training (use distributed XGBoost) or simplify model
- **Kafka rebalancing frequency > 1x per week:** Increase broker count (6 brokers) or optimize partition assignment
- **PostgreSQL query latency > 150ms for experiment reads:** Shard by experiment_id or move hot data to cache
- **Recommendation latency p95 > 120ms:** On-device model inference needs optimization or fallback ranking improvement

---

## 10x Scenario (2M DAU, 10M recommendations/day)

### Market Reality at 10x

- **Enterprise scale:** Platform serving 2M active users (major consumer app or regional player)
- **Test velocity explosion:** 500+ concurrent A/B tests (experimentation platform becomes critical)
- **Real-time personalization:** Recommendations must update in <5 seconds (interactive browsing)
- **Regulatory load:** Large user bases trigger data privacy requirements (GDPR, CCPA)

### What's Fundamentally Broken at 10x

1. **Feature store doesn't scale** — 2M DAU * 50KB profile = 100GB storage needed; even distributed feature store struggles. Caching only hot 50K users leaves 1.95M users with stale features (updated every 24h instead of <10min)

2. **Kafka becomes bottleneck** — 10M recommendations/day * 3 byte retention = 30M messages; Kafka cluster disk I/O becomes maxed out. Message order guarantees degrade under load.

3. **Spark job duration explodes** — Training complexity doesn't grow linearly; with 10x data, training time could be 8-12 hours; overlaps completely with recommendation window; feature staleness becomes problem

4. **PostgreSQL can't handle experiment complexity** — 500 concurrent tests mean 500K+ experiment assignments per day; query latency exceeds 500ms; metadata lookups become bottleneck

### Architectural Changes Needed for 10x

| Problem | 1x/2x Solution | 10x Solution |
|---------|---|---|
| **Feature store** | In-memory (Redis-like) | Distributed feature store (Tecton, Feast); partition by user cohort; lazy loading from cold storage |
| **Model training** | Batch Spark jobs (daily) | Incremental learning; online learners (river, vowpal wabbit); update model in real-time |
| **Kafka** | Single cluster (3-5 brokers) | Multi-cluster (regional); async replication; local event buffering on client |
| **Experiment metadata** | Single PostgreSQL table | Distributed experiment registry; time-series database for variant performance tracking |
| **Batch processing** | Spark cluster | Stream processing (Flink) for real-time model updates; batch processing (Spark) only for overnight aggregation |

### Cost at 10x (Realistic Projection)

| Category | 1x | 10x | Ratio |
|----------|----|----|-------|
| Compute (API servers) | $2.4K | $18K | 7.5x |
| Kafka (multi-region) | $2.1K | $12K | 5.7x |
| Feature store (distributed) | $1.8K | $15K | 8.3x |
| ML serving (global) | $1.5K | $12K | 8x |
| Stream processing (Flink) | $0 | $8K | ∞ |
| Spark (on-demand) | $2.8K | $5K | 1.8x |
| Database (distributed) | $0.8K | $8K | 10x |
| Data warehouse (analytics) | $0 | $10K | ∞ |
| **Total** | **$12.0K** | **$88K** | **7.3x** |

**Cost scales sub-linearly (7.3x cost for 10x volume) due to economies of scale and architectural shifts toward streaming.**

---

## Capacity Planning Roadmap

| Quarter | Trigger Level | Action | Investment |
|---------|---|---|---|
| Q2 2026 | Monitor 2x | Pre-stage API + Kafka infrastructure; Spark cluster optimization | $3K |
| Q3 2026 | Approach 2x (300K DAU) | Add Kafka brokers; implement feature cache tiering | $8K + 250 eng hours |
| Q4 2026 | Hit 2x (400K DAU) | Full 2x deployment; Spark job parallelization | Ongoing ops |
| Q1 2027 | Plan 5x (1M DAU) | Distributed feature store evaluation (Tecton/Feast); stream processing POC | 400 eng hours |
| Q2 2027+ | 5x+ territory | Execute 10x roadmap; Flink migration; distributed experiment platform | $60K infra + 1500 eng hours over 6 months |

