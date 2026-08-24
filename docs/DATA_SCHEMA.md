# PAYGUARD ARENA — Data Schema

This document defines the schema for our synthetic payment world state generator (from SPEC.md Section 4). All models will train and evaluate exclusively on this synthetic data.

## Entity Schema

### User
| Name | Type | Meaning | How Generated | Available at Decision Time? |
|---|---|---|---|---|
| `user_id` | UUID | Unique identifier | Auto-generated ID | Y |
| `profile_attrs` | JSON | Demographics, location | Sampled from census distributions | Y |
| `created_at` | Timestamp | Account creation time | Set at creation | Y |
| `is_synthetic` | Boolean | True if created by Attack 1 | Flagged by simulation engine | N (Leakage) |

### Account
| Name | Type | Meaning | How Generated | Available at Decision Time? |
|---|---|---|---|---|
| `account_id` | UUID | Unique identifier | Auto-generated ID | Y |
| `user_id` | UUID | Foreign key to User | Assigned to creating user | Y |
| `opened_at` | Timestamp | Account opening time | Set when opened | Y |
| `status` | String | Active, Suspended, Closed | Mutated by simulation state | Y (at time of transaction) |

### Card
| Name | Type | Meaning | How Generated | Available at Decision Time? |
|---|---|---|---|---|
| `card_id` | UUID | Unique identifier | Auto-generated ID | Y |
| `account_id` | UUID | Foreign key to Account | Assigned to linked account | Y |
| `issued_at` | Timestamp | Card issuance time | Set when issued | Y |
| `status` | String | Active, Blocked | Mutated by simulation state | Y (at time of transaction) |

### Device
| Name | Type | Meaning | How Generated | Available at Decision Time? |
|---|---|---|---|---|
| `device_id` | UUID | Unique identifier | Auto-generated ID | Y |
| `user_id` | UUID | FK to first User seen | Linked on first login | Y |
| `first_seen` | Timestamp | First appearance in sim | Set on first transaction | Y |
| `trust_score` | Float | Reputation metric | Computed based on history | Y (Must only use past history) |

### IP
| Name | Type | Meaning | How Generated | Available at Decision Time? |
|---|---|---|---|---|
| `ip_id` | String | IP Address | Sampled from valid ranges | Y |
| `geo` | String | Region/Country | Mapped from IP | Y |
| `first_seen` | Timestamp | First appearance in sim | Set on first transaction | Y |
| `is_new_for_user` | Boolean | Novelty for given user | Computed per transaction | Y (Based only on past txns) |

### Merchant
| Name | Type | Meaning | How Generated | Available at Decision Time? |
|---|---|---|---|---|
| `merchant_id` | UUID | Unique identifier | Auto-generated ID | Y |
| `category` | String | MCC code/category | Sampled from distributions | Y |
| `trust_tier` | Int | Reputation level (1-5) | Configured in simulator | Y |

### Transaction (The Core Event)
| Name | Type | Meaning | How Generated | Available at Decision Time? |
|---|---|---|---|---|
| `txn_id` | UUID | Unique identifier | Auto-generated ID | Y |
| `account_id` | UUID | FK to Account | Sourced from actor | Y |
| `card_id` | UUID | FK to Card | Sourced from actor | Y |
| `device_id` | UUID | FK to Device | Sourced from actor | Y |
| `ip_id` | String | FK to IP | Sourced from actor | Y |
| `merchant_id` | UUID | FK to Merchant | Sampled by actor | Y |
| `amount` | Float | Transaction value | Sampled by actor / attack logic | Y |
| `timestamp` | Timestamp | Event time | Sim clock | Y |
| `channel` | String | Online, POS, ATM | Sourced from actor context | Y |
| `label` | String | Fraud / Legit | Simulation ground truth | **N (Leakage - Target Variable)** |
| `campaign_id` | UUID | FK to Campaign (if attack) | Linked if attack-generated | **N (Leakage - Implies Fraud)** |
| `round_id` | Int | Arena round number | Set by orchestrator | **N (Leakage - Not present in real life)** |

### Campaign (Attack Metadata)
*(None of these fields are available to the decision model)*
| Name | Type | Meaning | How Generated | Available at Decision Time? |
|---|---|---|---|---|
| `campaign_id` | UUID | Unique identifier | Auto-generated | N |
| `attack_type` | String | Synthentic, ATO, GenAI SE | Set by attacker agent | N |
| `phase` | String | Current phase of attack | Mutated by attacker agent | N |
| `objective` | String | Goal of the campaign | Set by attacker agent | N |
| `status` | String | Active, Caught, Success | Mutated by simulator | N |
| `round_id` | Int | Arena round number | Set by orchestrator | N |

---

## LEAKAGE RISKS — NEEDS HUMAN REVIEW

To strictly abide by the leakage hard-rule, the following considerations must be made for any derived features (like rolling averages or behavioral profiles):

1. **`Transaction.label`**: This is the ground truth. It can never be used in feature engineering.
2. **`Transaction.campaign_id`**: A non-null value here instantly flags the transaction as fraud originating from an attack. This must be masked or dropped before scoring.
3. **`Transaction.round_id`**: The model shouldn't know which "round" it is in, as this is a meta-simulation artifact.
4. **`User.is_synthetic`**: This is essentially a label for Attack 1 (Synthetic Identity). Using this directly leaks the fraud state.
5. **Behavioral Baselines**: Any aggregation (e.g., `user_avg_spend`) MUST only compute up to `Transaction.timestamp` - 1 tick. If we aggregate over a time window that includes the current transaction or future transactions, we leak future state.
6. **Device `trust_score` / IP `is_new_for_user`**: These must be updated *after* the transaction is scored. If the transaction itself influences the trust score which is then used to score that very same transaction, it causes leakage.
