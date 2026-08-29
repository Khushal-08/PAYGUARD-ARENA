# Future Extension: Relational Risk Module

## Overview
While the current Payguard Arena architecture successfully demonstrates real-time adaptive defense and achieves high evaluation scores across our core pillars, it deliberately evaluates transactions independently using our canonical 9-feature vector. This document outlines the planned **Relational Risk Module**, designed to align closely with Mastercard’s Decision Intelligence Pro philosophy by evaluating relationships across multiple entities (Accounts, Devices, IPs, and Merchants).

## Proposed Relational Features
An offline exploratory analysis against our simulated baseline data (`simulated_baseline.csv`) demonstrates the feasibility of generating robust, graph-like aggregate features without requiring complex Graph Neural Networks (GNNs). Key targeted features include:

- `device_unique_accounts_7d`: Flagging devices that rapidly cycle through synthetic identities.
- `ip_unique_accounts_24h`: Identifying velocity-based Account Takeover (ATO) bursts originating from single IPs.
- `merchant_unique_accounts_7d`: Identifying merchant concentration risk.
- `account_device_change_count`: Highlighting high-friction account behavior indicative of credential stuffing.
- `shared_device_risk`: Capturing contagion when known-bad entities interact with clean ones.

## Why This Was Deferred
We deliberately scoped this as a future production extension rather than running even the offline exploratory check now, heavily prioritizing submission-readiness and documentation quality in the final 3 days before the Mastercard Innovation Challenge deadline. 

The primary architectural challenges preventing live deployment in the current sprint are:

1. **Stateful Feature Store Requirement:** The current `/defend/score` endpoint is designed to be ultra-fast and completely stateless, relying on the client to provide the localized 9-feature array. Injecting temporal/relational constraints (e.g., a 7-day rolling window of unique accounts per device) into the live production path requires standing up a dedicated, low-latency Feature Store (such as Redis) to track cross-entity state histories at runtime.
2. **Canonical Baseline Integrity:** The current XGBoost model (`xgboost_baseline_round_1.pkl`), the baseline results, and the adaptive SHAP loop are intrinsically locked to the canonical 9 features. Mixing relational features into the current pipeline risks breaking the meticulously verified baseline metrics (`baseline_results.json`) right before submission.

## Implementation Path
When implemented, this module will exist as a **Config 4 Experiment** alongside the existing models. The Feature Store will act as a sidecar to the FastAPI backend, hydrating incoming transactions with relational context in sub-millisecond timeframes prior to XGBoost inference.
