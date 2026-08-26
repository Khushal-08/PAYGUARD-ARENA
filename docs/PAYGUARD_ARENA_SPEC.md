# PAYGUARD ARENA — Locked Technical Specification (v2)
**Mastercard Innovation Challenge 2026 · GFF 2026**

> Static fraud detectors are evaluated against yesterday's fraud. PAYGUARD ARENA continuously challenges a payment defense with adaptive, GenAI-generated attacks and measures how well the defense survives previously unseen attack variants.
>
> *We don't assume the attacker will repeat yesterday's fraud. We make the attacker adapt.*

**Changelog from v1:** added the IDENTIFY-pillar research taxonomy (Section 2), explicit agent action-spaces (Section 3), an attack-fidelity evaluation methodology (Section 6), locked scientific definitions + contamination controls (Section 9), an honest GenAI-signal ablation (Section 8), and a real-world feasibility narrative (Section 12). Architecture is unchanged — this version adds proof and rigor around it.

---

## 0. How to use this document

This is the single source of truth. Nobody re-derives architecture mid-build. If something isn't in here, raise it, decide it once, add it here, move on.

---

## 1. Core thesis & three pillars

| Pillar | What it means here |
|---|---|
| **IDENTIFY** | Documented GenAI-enabled payment fraud patterns, researched broadly (10–15+ vectors, Section 2) and cited from real threat intel — 3 selected for deep executable simulation. |
| **GENERATE** | LLM-driven attack agents that instantiate selected patterns as executable, stateful campaigns, with a signal-only adaptive loop (Section 5). |
| **DEFEND** | An ML + behavioral + graph + (ablated, optional) GenAI-signal risk engine that scores transactions and campaigns, explains its decisions, and adapts between rounds. |

**Claim discipline (non-negotiable):** We never claim to have discovered real-world fraud. We claim: *"Our red team generates previously unseen adversarial fraud variants within a controlled payment simulation, constrained to the same information a real adversary would have, and we measure how a defense's detection rate degrades and recovers against them."*

---

## 2. IDENTIFY pillar — research taxonomy (write this up, don't build all of it)

Strategy locked: **research 10–15+ vectors broadly, implement 3 deeply.** This satisfies "diversity of attacks identified" without diluting engineering time. Deliverable: a short taxonomy section in the solution docx, citing real sources (Mastercard, FINRA, Federal Reserve) and clearly separating *documented real-world threats* from *our own attack-instance design*.

| Attack | Payment surface | Role of GenAI | Status |
|---|---|---|---|
| Synthetic identity | Account onboarding | Generates plausible-but-fake identity attributes at scale | **Implement** |
| Account takeover / behavioral hijacking | Existing account | Automates credential stuffing / mimics prior behavior | **Implement** |
| GenAI social engineering | Payment authorization | Generates personalized, persuasive scam scenarios | **Implement** |
| Mule-network orchestration | Fund movement | Coordinates multi-account cash-out timing | Research-only (4th attack only if Day 6 checkpoint is ahead) |
| Deepfake KYC/liveness bypass | Identity verification | Synthetic video/audio for liveness checks | Research-only — no video pipeline in 9 days |
| Card testing / enumeration bots | Card-not-present checkout | Varies testing patterns to evade rate limits | Research-only |
| Adversarial perturbation against the fraud model itself | ML pipeline | Perturbs features to cross the decision boundary | Research-only — worth one sentence as "future work," shows awareness of your own model's attack surface |
| GenAI-scripted phishing/smishing | Pre-transaction | Mass-personalized lure generation | Research-only |

---

## 3. The three locked attack agents — as genuine agents, not row generators

Each agent must have an explicit action space and adaptation mechanism — not just a final fraud/legit label. This table is the implementation contract:

| | Synthetic Identity | Account Takeover | GenAI Social Engineering |
|---|---|---|---|
| **Objective** | Reach a fraud transaction undetected | Reach a payout undetected | Get an out-of-pattern payment authorized |
| **State observed** | Own campaign phase; risk signal from past actions | Established baseline; compromise status | Victim profile; prior scenario acceptance/rejection |
| **Actions** | Advance phase; adjust drift rate/amount/timing | Choose device/IP; choose deviation magnitude | Choose persuasion angle, urgency level, target amount |
| **Constraints** | Must pass through all phases in order | Must establish baseline before deviating | Must stay within victim's plausible context |
| **Reward** | Undetected progress toward objective transaction | Same | Same |
| **Adaptation mechanism** | LLM reasoning over defense signal (Section 5) → phase/parameter change | Same | Same, applied to scenario-generation strategy |
| **Stopping condition** | Objective transaction attempted (success or caught) | Same | Same |

**Campaign phases (unchanged from v1):**
- **Synthetic Identity:** identity creation → account opening → card issuance → normal-looking seeding → gradual drift → fraud attempt.
- **Account Takeover:** baseline established → compromise event → behavior shift → fraud attempt → cash-out.
- **GenAI Social Engineering:** victim profiling → scenario generation → simulated victim decision (probabilistic, based on a defined and justified persuasiveness score) → authorization → transaction → detection.

---

## 4. Payment world — state model

*(Unchanged from v1 — see below)*

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

Every transaction changes state live (velocity, device trust, behavioral baseline) — features must be computed from state, not hand-authored.

---

## 5. Data strategy, schema & leakage rules — Day 1, not the end

**Resolved data question (confirmed against official competition rules, Section 3(a)):** Participants are required to *"use only synthetic, anonymized or authorized sample data and not use any real cardholder, PII or production payment data."* This is a build-a-system challenge judged by a panel, not a classic Kaggle leaderboard competition with a provided labeled dataset. There is no confirmed official transactional dataset for this event. **Our own simulator's generated output (Section 4) is the primary data source for the entire project.** This was verified against the Kaggle discussion thread on [date] — if that changes, this section gets revised, not the other way around.

**Role of a public reference dataset (e.g. IEEE-CIS Fraud Detection, PaySim):** used **only** as an external distributional reference for the fidelity check in Section 6 (does our synthetic legitimate-transaction baseline look statistically similar to real-world payment behavior?). Never labeled, presented, or treated as "the" competition dataset, and never used to train the actual defense — that would undermine the claim discipline in Section 1.

Deliverable: `DATA_SCHEMA.md`, built against our own simulator's generated schema (Section 4), documenting for every field: `name | type | meaning | how it's generated | available_at_decision_time (Y/N)`.

**Hard rule:** no feature may use information only available after the decision. Banned unless proven pre-decision: `fraud_confirmed`, `chargeback_status`, `future_transaction_count`, any post-investigation label, any window aggregate including future transactions. This rule applies to our own simulator's generated fields exactly as it would to a real dataset — it's easy to accidentally leak future state into a feature when you control the generator.

---

## 6. Attack fidelity — evaluation methodology (new, required)

"It looks realistic" is not evidence. Minimum credible methodology:

1. Generate synthetic **legitimate** baseline transactions from the simulator.
2. Run a KS-test or Jensen-Shannon divergence comparing your synthetic distributions (transaction amount, hour-of-day, merchant category) against the same distributions in a public reference dataset (e.g. IEEE-CIS Fraud Detection), used strictly as an external real-world reference per Section 5 — not as a training set, and not claimed as official competition data.
3. Report divergence numbers plainly in the docx. This validates that the *legitimate baseline* the fraud has to hide inside of is statistically realistic — it does **not** claim the fraud itself is real-world-validated, since no ground truth exists for GenAI fraud.
4. For attack campaigns, validate **internal consistency** instead: phase-duration distributions, smoothness of behavioral drift (no step-function jumps), objective-transaction size relative to the account's own baseline.
5. Explicitly do NOT compare synthetic attacks against real fraud rows to claim realism — that would be an unsupported claim. Compare only what's provably comparable (the legitimate baseline).

---

## 7. Blue team architecture (defense)

```
Transaction features (rule/velocity based)
        +
Behavioral features (deviation from user baseline)
        +
Graph features (NetworkX — shared device/IP/merchant links; skip GNN)
        +
[OPTIONAL, ABLATED] GenAI signal (Section 8)
        ↓
   Risk fusion (XGBoost/LightGBM)
        ↓
   APPROVE / REVIEW / BLOCK
        ↓
   SHAP explanation layer
```

Locked decision: tree-based fusion + SHAP, not a GNN/transformer/sequence model. This is the strongest architecture provably finishable and explainable in 9 days — explainability is itself a scored dimension (real-world feasibility), and SHAP-on-trees is fast and legible where a GNN's decision would not be in a live demo.

**On using published approaches:** reading winning write-ups from related fraud-detection competitions for feature-engineering *patterns* (entity-grouping/UID features, frequency encoding, time-since-last aggregates) is encouraged and cited in `REFERENCES.md`. Copying notebook code or a trained model wholesale is not permitted — it breaches the competition's originality warranty, and a borrowed model trained on a different schema/task doesn't transfer to our simulator's data without a full retrain anyway, so there's no actual shortcut available. Every feature and model in the defense stack must be our own implementation, inspired by cited public sources where relevant.

---

## 8. GenAI defense-signal — honest ablation (new, required)

Do not assume the GenAI signal helps. Test it:

```
Defense WITHOUT GenAI signal:  transaction + behavioral + graph → XGBoost
Defense WITH GenAI signal:     above + LLM impersonation/social-engineering signal → XGBoost
```

Compare both on: known/unseen/adaptive detection rate, false positive rate, latency, and per-transaction LLM cost. **Report the result honestly either way.** If the signal adds negligible lift, say so and keep it optional — "we tested whether GenAI improves detection and found [X], so we made it opt-in" is a stronger statement to a skeptical judge than silently keeping a decorative feature.

---

## 9. Locked definitions & contamination control (new, required)

Use these definitions verbatim in the docx and code comments:

- **Known attack:** an instance present in the training distribution of the current defense version.
- **Unseen attack:** a generated instance withheld from that training set — same attack type, different instantiation.
- **Adaptive attack:** an instance generated using feedback (SHAP/rule signal) from the defense's decision on a prior-round instance.
- **Attack success:** the campaign's objective transaction is not blocked/flagged for review.
- **Detection:** the risk engine flags the objective transaction (or an earlier phase) as REVIEW/BLOCK.
- **Robustness recovery:** the delta in adaptive-attack detection rate before vs. after one retrain cycle.

**Contamination control:** tag every generated instance with `round_id`; freeze a fixed validation set *before* Round 1 that never receives generated data from any round; version-tag model checkpoints per round so every number is traceable to the model that produced it.

---

## 10. Baseline ladder & experiment matrix

| # | System | Tested against |
|---|---|---|
| 1 | Rules only | Known |
| 2 | XGBoost | Known |
| 3 | XGBoost + behavioral | Known + unseen |
| 4 | XGBoost + graph | Known + unseen |
| 5 | Full fusion (Section 7) | Known + unseen + adaptive |

**Full matrix:** 5 configs × 3 test-set types = 15 cells, plus the 3-round adaptive table (Round 1/2/3 detection rate, reported exactly as measured — do not pre-target a number), plus the 2-row GenAI-signal ablation (Section 8). This is the entire evidence package needed — nothing more, nothing less.

---

## 11. Evaluation metrics (headline: **Adversarial Robustness**, not accuracy)

Known-attack detection rate · unseen-variant detection rate · adaptive-attack detection rate (round-over-round) · false positive rate · time-to-detection · attack success rate · GenAI-signal ablation delta.

---

## 12. Real-world feasibility narrative (new — cheap, high-leverage, currently worth zero)

Write one page/diagram in the docx covering:
- Tree-model inference kept under ~50ms on the authorization path.
- LLM calls **off** the blocking path — batch-generate social-engineering signals, never call an LLM per live transaction.
- A REVIEW tier + step-up authentication (OTP/biometric) instead of hard blocking, to address false positives.
- SHAP output feeding compliance/dispute workflows.
- Stated retrain cadence and drift monitoring (e.g., population-stability-index style).
- Synthetic-data-only privacy posture.
- Stateless scoring service for horizontal scale.

This is writing, not engineering — do it while waiting on training runs, not as an afterthought.

---

## 13. API contracts

```
POST /simulate/campaign        → { attack_type, victim_profile? } → campaign_id
GET  /simulate/campaign/{id}   → campaign state + generated transactions
POST /defend/score              → { transaction } → { risk_score, decision, shap_top_features }
POST /adapt/attack               → { campaign_id, defense_signal } → new campaign_id (mutated)
POST /adapt/defense               → retrain trigger → new model version id
GET  /arena/round/{n}            → { attack, detection_rate, explanation } for dashboard replay
```

Pre-compute and cache round outputs for the live demo — never depend on a live LLM call succeeding in front of judges.

---

## 14. Three-screen UI

*(Note: The frontend code lives in the `dashboard/` directory, configured for Vercel deployment, not `/app/frontend` as previously planned.)*

1. **Arena / Battle view** — round-by-round animation, including the actual LLM reasoning text behind each mutation (this is your proof of genuine adaptation, make it visible).
2. **Transaction / Case view** — flagged transaction with SHAP explanation + campaign trace.
3. **Evidence / Metrics dashboard** — baseline ladder + adversarial robustness metrics + ablation result.

---

## 15. Demo script (works regardless of the actual numbers)

- **0–10s:** "Every fraud detector is tested against yesterday's fraud. Ours is tested against tomorrow's." Arena screen, Round 1 about to launch.
- **10–40s:** Attack launches, detection rate shown as measured.
- **40–70s:** Show the captured decision signal and the actual LLM reasoning text, then the Round 2 mutated attack and its (likely lower) detection rate — narrate the dip as the interesting part, not a flaw.
- **70–100s:** Defense retrains, Round 3, recovered detection rate — real number.
- **100–140s:** Case view — one flagged transaction with SHAP explanation.
- **140–170s:** Evidence dashboard — baseline ladder + ablation result.
- **170–180s:** Close: *"Round 1, our AI attacker gets caught. Round 2, it figures out why — and comes back smarter. Watch what happens."*

---

## 16. Ownership — solo build

Built solo, using Antigravity to execute individual missions sequentially rather than across parallel teammates. This changes pacing, not scope — every component in Sections 1–15 still applies. The practical adjustment: work moves in a strict sequence (finish and verify one piece before starting the next) rather than three tracks running simultaneously, and every "someone reviews someone else's output" checkpoint in this spec becomes "come back with fresh eyes before approving," especially for the two highest-risk categories: (a) anything claiming a suspiciously clean number (the 99.97% AUC and 0.00% detection incidents both came from trusting a result too quickly), and (b) anything the adaptive loop or an attack agent claims is "genuine reasoning" or "genuine adaptation" — verify by reading the actual output, not the summary of it.

Given no second reviewer exists, build in a personal checkpoint before accepting any walkthrough as done: does the number look too good, and does the described mechanism actually match what's shown in the raw output (JSON trace, reasoning text, feature values)? This has caught three real bugs already; going solo makes it more important, not less.

---

## 17. 9-day task board

**Day 1** — Confirm data strategy on the Kaggle discussion thread (Section 5). Payment world's generated schema documented as `DATA_SCHEMA.md` + leakage audit against our own generator. Target/split decided for internal training/eval. **Attack taxonomy research doc started** (Section 2).
**Day 2** — Payment world state model implemented. Rules + XGBoost baseline running. **Fidelity-test scaffolding** (KS-test/JS-divergence script) written against placeholder data.
**Day 3** — Behavioral features. Attack 1 (Synthetic Identity) generating full campaigns with explicit phase/action logging.
**Day 4** — Attack 2 (Account Takeover). Baseline ladder experiments 1–3. Taxonomy doc finalized.
**Day 5** — **MVP checkpoint.** Simulator + XGBoost + behavioral features + 2 attack generators + fraud scoring + basic dashboard working end to end. If not real, cut scope before adding anything below.
**Day 6** — Attack 3 (GenAI Social Engineering). Graph features. SHAP integration. Fidelity report run for real.
**Day 7** — Adaptive loop (signal-only, LLM reasoning visible). Defense retrain → Round 3. GenAI-signal ablation run.
**Day 8** — Full Arena UI, demo rehearsal, cache round outputs, feasibility narrative written, solution docx drafted, code frozen.
**Day 9** — Buffer only. Fix bugs found in rehearsal. No new features.

---

## 18. Kill list

**MUST BUILD:** stateful simulator + 3 attack agents with inspectable, action-space-driven campaign traces; the 3-round signal-only adaptive loop with real numbers and visible LLM reasoning; the 3-screen dashboard with cached replay.
**NICE TO HAVE:** 4th attack (mule network); the GenAI-signal ablation as a polished chart; the fidelity report visualized rather than tabular.
**CUT COMPLETELY:** GNNs/transformers/sequence models, RAG, live production auth/deployment, mobile app, microservices/K8s, multi-agent orchestration beyond the three attack agents, UI animation polish beyond the Arena screen.

---

## 19. What you say when a judge pushes back

- *"Why GenAI, not a conventional fraud model?"* → The social-engineering attack and the signal-driven mutation step are fundamentally GenAI-native; a rules engine can't generate a persuasion scenario or reason about why it got caught.
- *"Is your adaptive loop actually novel, or just adversarial training?"* → The loop shape is standard adversarial ML. What's different: the attacker only ever sees the defense's decision signal, never the label — mirroring real adversary knowledge — and an LLM produces visible, inspectable reasoning for each mutation, not a fixed strategy table.
- *"How do you know your attacks are novel?"* → We don't claim real-world novelty. Novelty is defined as "not present in the current defense's training distribution" (Section 9), and we measure detection rate against exactly that definition.
- *"How do you prove your simulation is realistic?"* → Section 6: we statistically compare our synthetic legitimate baseline against real competition data, and validate attack campaigns for internal consistency — we do not claim fraud-instance realism we can't prove.
- *"Does the GenAI signal in your defense actually help?"* → We ran the ablation (Section 8) and report the result honestly — it's optional/opt-in based on what we measured, not assumed.
- *"How does this work in a live payment system?"* → Section 12: sub-50ms tree inference on the blocking path, LLM calls off that path, REVIEW tier with step-up auth instead of hard blocking.
