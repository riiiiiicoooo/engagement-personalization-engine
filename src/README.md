# Source Code: Reference Implementation

> **Note:** This code is a PM-authored reference implementation demonstrating the core technical concepts behind the Engagement & Personalization Engine. It is not production code. These prototypes were built to validate feasibility, communicate architecture to engineering, and demonstrate technical fluency during product development.

## Contents

| File | Purpose |
|---|---|
| `segmentation/user_segmenter.py` | Real-time user segmentation: lifecycle stage, behavioral cohort, engagement tier, goal cluster |
| `scoring/engagement_scorer.py` | Composite engagement score (0-100): recency, frequency, depth, consistency, progression |
| `recommendations/recommendation_engine.py` | Two-stage content ranking: candidate generation + weighted scoring with diversity enforcement |
| `experiments/experiment_framework.py` | A/B test assignment (deterministic hashing), exposure logging, guardrail monitoring, sequential testing |
| `flags/feature_flags.py` | Feature flag evaluation: rollout percentage, segment targeting, kill switch, audit logging |

## How These Were Used

As PM, I wrote these prototypes to:

1. **Validate the scoring algorithm** — tested weight configurations against historical churn data to find the combination that maximized AUC (0.84 with current weights vs. 0.76 with equal weights)
2. **Prove latency feasibility** — benchmarked the personalization pipeline end-to-end to confirm < 100ms was achievable before committing to real-time architecture
3. **Spec the experiment system** — implemented deterministic hashing and validated uniform distribution across 1M synthetic user IDs before engineering built the production version
4. **Model intervention economics** — built the scoring + intervention pipeline to quantify the value of real-time detection vs. daily batch (38% vs. 14% intervention success rate)
5. **Communicate with engineering** — working code conveys intent more precisely than requirements documents alone
