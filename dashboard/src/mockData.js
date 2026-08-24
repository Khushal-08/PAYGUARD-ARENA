// TEMPORARY_MOCK_DATA: mirrors the trimmed demo payload for UI development only. Replace with GET /arena/round/{n} from FastAPI (SPEC.md §13).
export const demoData = {
  "round_1_detection_rate": 0.989010989010989,
  "round_1_caught": 90,
  "round_1_total": 91,
  "round_1_avg_amt": 1507.80,
  "round_0_model_fpr": 0.0043,
  "round_0_model_fp_count": 196,
  "round_0_model_total_legit": 45476,
  "shap_explanation": [
    ["amount", 6.2212],
    ["account_time_since_last_txn", 0.9138],
    ["hour_of_day", 0.4545],
    ["is_familiar_merchant", 0.3201],
    ["device_txns_7d", 0.1504]
  ],
  "llm_reasoning": "The high SHAP score for 'amount' required drastically reducing fraud_avg_amt_loc to the 3x minimum threshold while raising baseline spending. To evade 'account_time_since_last_txn' detection, we increased seeding count and reduced delays. Adopting a 'blend_peak' timing strategy neutralizes 'hour_of_day' signals.",
  "mutated_params": {
    "seeding_count_loc": 20,
    "seeding_delay_loc": 18,
    "drift_avg_amt_loc": 250,
    "drift_delay_loc": 4,
    "fraud_avg_amt_loc": 750,
    "timing_strategy": "blend_peak"
  },
  "round_2_detection_rate": 0.9275,
  "round_2_caught": 371,
  "round_2_total": 400,
  "round_2_avg_amt": 740.46,
  "round_3_detection_rate": 0.9875,
  "round_3_caught": 79,
  "round_3_total": 80,
  "round_3_avg_amt": 752.71,
  "round_1_model_fpr": 0.0086,
  "round_1_model_fp_count": 393,
  "round_1_model_total_legit": 45476
};

// Mock transaction feed simulating the attacks hitting the model
export const mockTransactions = [
  { id: 'tx-1', time: '10:02:14', amount: 1250.00, attackType: 'Synthetic Identity', status: 'caught', reason: 'Anomalous amount + new device' },
  { id: 'tx-2', time: '10:02:45', amount: 45.00, attackType: 'Legitimate', status: 'passed', reason: '' },
  { id: 'tx-3', time: '10:05:12', amount: 740.50, attackType: 'Account Takeover', status: 'caught', reason: 'High velocity (account_txns_24h)' },
  { id: 'tx-4', time: '10:08:33', amount: 750.00, attackType: 'Account Takeover', status: 'missed', reason: 'Blended with peak hours' },
  { id: 'tx-5', time: '10:12:05', amount: 3500.00, attackType: 'Social Engineering', status: 'caught', reason: 'SHAP[amount] exceeded threshold' },
  { id: 'tx-6', time: '10:14:22', amount: 15.00, attackType: 'Legitimate', status: 'passed', reason: '' },
];
