# PAYGUARD ARENA — Locked Technical Specification
**Mastercard Innovation Challenge 2026 · GFF 2026**

> Static fraud detectors are evaluated against yesterday's fraud. PAYGUARD ARENA continuously challenges a payment defense with adaptive, GenAI-generated attacks and measures how well the defense survives previously unseen attack variants.
>
> *We don't assume the attacker will repeat yesterday's fraud. We make the attacker adapt.*

---

## 0. How to use this document

This is the single source of truth. Nobody re-derives architecture mid-build. If something isn't in here, raise it, decide it once, add it here, move on. Everyone builds from this, not from memory of the chat threads.

---

## 1. Core thesis & three pillars

| Pillar | What it means here |
|---|---|
| **IDENTIFY** | Documented GenAI-enabled payment fraud patterns (synthetic identity, account takeover, GenAI-powered social engineering) sourced from real threat intel (Mastercard, FINRA, Federal Reserve publications) — cited, not invented. |
| **GENERATE** | LLM-driven attack agents that instantiate those patterns as executable campaigns inside a stateful synthetic payment environment, and that adapt their strategy based on the defense's response. |
| **DEFEND** | An ML + behavioral + graph + GenAI-signal risk engine that scores transactions and campaigns, explains its decisions, and can be retrained/adapted between rounds. |

**Claim discipline (non-negotiable):** We never claim to have discovered real-world fraud. We claim: *"Our red team generates previously unseen adversarial fraud variants within a controlled payment simulation, and we measure how a defense's detection rate degrades and recovers against them."* That claim is provable in 9 days. The other one isn't.

---

## 2. The three locked attack agents

Build exactly these three. A 4th (mule network) is optional and only if 1–3 are solid by Day 6.

### Attack 1 — Synthetic Identity
**Objective:** establish an identity that looks legitimate, build transaction history, then execute a fraudulent transfer while minimizing detection risk.
**Campaign phases:** identity creation → account opening → card issuance → normal-looking transaction seeding → gradual behavior drift → fraud attempt.

### Attack 2 — Account Takeover / Behavioral Hijacking
**Objective:** simulate a legitimate user's account being compromised, with behavior diverging from the user's established baseline just enough to attempt a payout.
**Campaign phases:** baseline established → compromise event (new device/IP) → behavior shift → fraud attempt → cash-out.

### Attack 3 — GenAI Social Engineering (your strongest differentiator — do not cut this one)
**Objective:** given a synthetic victim profile (typical merchants, spend range, location), an LLM agent generates a persuasion scenario designed to get the victim to authorize an out-of-pattern payment.
**Campaign phases:** victim profiling → scenario generation → simulated victim decision (probabilistic, based on scenario "persuasiveness" score) → payment authorization → transaction → detection.
**Why this one matters most:** it's the one attack that is *distinctly* GenAI-powered rather than "fraud pattern that existed before LLMs." It's the direct answer to "why do you need GenAI at all."

### The Adaptive Layer (applies across all three, and is the actual centerpiece)
After each round, the attacker receives the defense's decision signal (SHAP feature importances or rule triggers — NOT the ground-truth label). An LLM reasoning step proposes a concrete strategy change (e.g., "detection triggered mainly on amount deviation → lower amount, raise frequency, use an already-trusted merchant"). This must produce an actually different attack instance, not a scripted if/else branch — verify by inspecting the generated campaigns, not just the metric.

---

## 3. Payment world — state model

Minimal entity set, all stateful, all synthetic:

```
User        { user_id, profile_attrs, created_at, is_synthetic }
Account     { account_id, user_id, opened_at, status }
Card        { card_id, account_id, issued_at, status }
Device      { device_id, user_id, first_seen, trust_score }
IP          { ip_id, geo, first_seen, is_new_for_user }
Merchant    { merchant_id, category, trust_tier }
Transaction { txn_id, account_id, card_id, device_id, ip_id, merchant_id,
              amount, timestamp, channel, label(fraud/legit),
              campaign_id (nullable), round_id (nullable) }
Campaign    { campaign_id, attack_type, phase, objective, status, round_id }
```

Every transaction changes state (account velocity, device trust, behavioral baseline). This is what makes it a simulation rather than a static labeled dataset — features are computed live from state, not hand-authored.

---

## 4. Data schema & leakage rules — DO THIS ON DAY 1, NOT AT THE END

Deliverable: `DATA_SCHEMA.md` produced collaboratively before any model code is written.

For every column: `name | type | meaning | missing % | example | available_at_decision_time (Y/N)`.

**Hard rule:** No feature may use information that only exists after the transaction decision. Explicitly banned unless proven available pre-decision: `fraud_confirmed`, `chargeback_status`, `future_transaction_count`, any post-investigation label, any aggregate computed over a window that includes future transactions.

Do this leakage pass **on Day 1–2**, with the whole team, not solo "at the end." A leakage bug found at hour 190 cannot be fixed. One found at hour 10 can.

---

## 5. Blue team architecture (defense)

```
Transaction features (rule/velocity based)
        +
Behavioral features (deviation from user baseline)
        +
Graph features (NetworkX — shared device/IP/merchant links; skip GNN)
        +
GenAI signal (LLM answers: "is this scenario consistent with impersonation
              / social engineering?" — a signal, NOT the final decision)
        ↓
   Risk fusion (XGBoost/LightGBM on combined features)
        ↓
   APPROVE / REVIEW / BLOCK
        ↓
   SHAP explanation layer
```

The LLM is a *signal generator*, never the fraud/not-fraud decision-maker. Keep that boundary explicit — it's a common judge objection ("how do you avoid hallucinations deciding real transactions?") and this architecture answers it directly.

---

## 6. Baseline ladder (this is your evidence, not a slide of "94% accuracy")

| # | System | Tests against |
|---|---|---|
| 1 | Rules only | Known fraud |
| 2 | XGBoost | Known fraud |
| 3 | XGBoost + behavioral features | Known + unseen |
| 4 | XGBoost + graph features | Known + unseen |
| 5 | Full PAYGUARD (+ GenAI signal) | Known + unseen + adaptive |

Then, separately, run the **adversarial rounds**:

```
Round 1: Attack generated          → Detection rate: X%
Round 2: Attacker adapts (uses SHAP signal) → Detection rate: Y%
Round 3: Defense retrains on round-2 patterns → Detection rate: Z%
```

Report whatever X/Y/Z actually come out — do not pre-decide the numbers. A real, modest result ("we degraded from 91% to 68% and recovered to 85% after one retrain") is more credible than a suspiciously perfect one.

---

## 7. Evaluation metrics (headline: **Adversarial Robustness**, not accuracy)

- Known-attack detection rate
- Unseen-variant detection rate
- Adaptive-attack detection rate (round-over-round)
- False positive rate
- Time-to-detection
- Attack success rate (attacker's own KPI — useful to show both sides)

---

## 8. API contracts (minimal, lock these so nobody blocks on integration)

```
POST /simulate/campaign        → { attack_type, victim_profile? } → campaign_id
GET  /simulate/campaign/{id}   → campaign state + generated transactions
POST /defend/score              → { transaction } → { risk_score, decision, shap_top_features }
POST /adapt/attack               → { campaign_id, defense_signal } → new campaign_id (mutated)
POST /adapt/defense               → retrain trigger → new model version id
GET  /arena/round/{n}            → { attack, detection_rate, explanation } for dashboard replay
```

Pre-compute and cache round outputs for the live demo — never depend on a live LLM call succeeding in front of judges. Replay cached real results; narrate it as live.

---

## 9. Three-screen UI

1. **Arena / Battle view** — round-by-round animation: attack launched → detection rate → attacker adapts → defense adapts. This is the memorable screen.
2. **Transaction / Case view** — a single flagged transaction with SHAP explanation, campaign trace (which entities/edges it touches).
3. **Evidence / Metrics dashboard** — the baseline ladder chart + adversarial robustness metrics from Section 7.

---

## 10. Team responsibilities (locked)

- **You — AI/ML + adversarial system:** XGBoost, feature engineering, behavioral + graph features, risk fusion, SHAP, adaptive-attack/defense loop logic, evaluation.
- **Person B — Red team + simulation:** payment world state engine, three attack agents, campaign mutation logic.
- **Person C — Product/integration:** FastAPI, React dashboard, three screens, demo orchestration, caching for live demo.

Everyone reviews everyone else's output before submission — especially the leakage check and the "is the adaptation actually adaptive" check.

---

## 11. 9-day task board

**Day 1** — Kaggle data pulled, understood as a team. `DATA_SCHEMA.md` drafted. Target definition + train/val/test split decided. Leakage-risk columns flagged.
**Day 2** — Payment world state model implemented (Section 3). Rules baseline + XGBoost baseline running end to end.
**Day 3** — Behavioral features. Attack 1 (Synthetic Identity) generating full campaigns into the state model.
**Day 4** — Attack 2 (Account Takeover). Baseline ladder experiments 1–3 running.
**Day 5** — **MVP checkpoint.** Synthetic payment environment + XGBoost + behavioral features + at least 2 attack generators + fraud scoring + basic dashboard must work end to end. If this doesn't work, cut scope further before adding anything below.
**Day 6** — Attack 3 (GenAI Social Engineering). Graph features. SHAP integration.
**Day 7** — Adaptive loop: attacker receives SHAP/rule signal, LLM proposes mutation, produces round 2. Defense retrain producing round 3.
**Day 8** — Full Arena UI, demo script rehearsal, cache round outputs, write the solution doc (.docx), freeze code.
**Day 9** — Buffer only. Fix bugs found in rehearsal. Do not add features.

---

## 12. Kill list (cut ruthlessly if behind schedule)

RAG system, 5+ agents, multi-agent orchestration frameworks, large knowledge bases, microservices/Kubernetes, GNN (NetworkX features are enough), elaborate auth, mobile app, unnecessary animation. None of these move the needle with judges; a working adaptive loop does.

---

## 13. What you say when a judge pushes back

- *"Why GenAI, not a conventional fraud model?"* → The social-engineering attack (Section 2, Attack 3) and the adaptive-mutation step (Section 2, Adaptive Layer) are both fundamentally GenAI-native; a rules engine can't generate a persuasion scenario or reason about *why* it got caught and propose a new strategy.
- *"How do you know your attacks are novel?"* → We don't claim real-world novelty. We define novelty as "not present in the training distribution of the current defense," and measure detection rate against exactly that definition (Section 6).
- *"How do you avoid hallucination affecting real decisions?"* → The LLM only ever produces a signal into the risk-fusion model (Section 5); XGBoost makes the decision.
