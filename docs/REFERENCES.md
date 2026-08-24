# PAYGUARD ARENA — References & Literature

This document logs external research, papers, and write-ups that inform our feature engineering and simulation methodology. Code is implemented from scratch; these references inform *patterns* only.

## 1. IEEE-CIS Fraud Detection (1st Place Solution)
- **Authors:** Konstantin Yakovlev & Chris Deotte (2019)
- **Source:** [1st Place Solution - Part 2 (Kaggle)](https://www.kaggle.com/competitions/ieee-fraud-detection/writeups/fraudsquad-1st-place-solution-part-2)
- **Summary:** The winning team treated fraud detection as an entity-classification problem ("finding UIDs") rather than isolated transaction classification. They used extensive EDA to group missing values, dropped temporally inconsistent features, and relied heavily on entity-level aggregations (frequency, recency, time-since-last-transaction) to track client behavior. They also used multiple diverse validation splits (e.g., skip-month, group-k-fold on time) because no single validation split was robust.
- **Pattern Adaptation for PAYGUARD:** 
  - We do not need to heuristically "find UIDs" since our simulator provides ground-truth entity IDs (User, Account, Device, Merchant). 
  - We will adapt their aggregate feature patterns (frequency, recency, merchant familiarity) directly to our deterministic schema (`ml/features/entity_aggregates.py`).
  - We will implement their "time-consistency" check during feature selection: evaluate individual features across time-splits and drop those whose validation AUC collapses (`ml/evaluation/time_consistency.py`).
  - We will adopt their rigorous multi-split validation strategy rather than relying on a single temporal holdout.
  - *No code from this solution is copied or used.* We enforce tree-based single-model inference rather than their stacking/ensembling per our strict inference budget (SPEC.md Section 7).

## 2. Responsible AI in Phishing & Social Engineering Simulation
- **Reference:** Industry standard practices (e.g. KnowBe4, Phished) for security awareness training.
- **Summary:** Major security simulation platforms use curated, human-authored template libraries combined with data-driven personalization to generate plausible attacks at scale. Live generative AI is generally avoided in fully automated offensive content pipelines to mitigate safety risks and prevent the uncontrolled creation of novel, actionable malicious material.
- **Pattern Adaptation for PAYGUARD:**
  - In Attack 3 (Social Engineering), we redesigned the pipeline from a live LLM-generated persuasion engine to a fixed, human-authored taxonomy of attack categories (e.g., "fake fraud alert", "account block threat").
  - Target personalization remains highly dynamic and data-driven—heuristically matching the victim's active hours, spending cadence, and top merchants from their history—but the core strategy categories are structurally constrained.
  - This responsible-AI design decision safely unblocks our rate-limit issues, letting us scale simulated campaigns indefinitely. More importantly, it mirrors real-world enterprise simulation design and aligns with the responsible AI and security disclosure practices highlighted in the competition rules (Section 3(c)).
