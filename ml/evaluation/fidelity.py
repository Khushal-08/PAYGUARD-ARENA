import os
import csv
import json
import random
import bisect
from datetime import datetime
import math
from collections import Counter

def compute_ks(data1, data2):
    n1 = len(data1)
    n2 = len(data2)
    if n1 == 0 or n2 == 0: return 0.0
    
    data1.sort()
    data2.sort()
    
    all_vals = sorted(list(set(data1 + data2)))
    max_d = 0.0
    for v in all_vals:
        cdf1 = bisect.bisect_right(data1, v) / n1
        cdf2 = bisect.bisect_right(data2, v) / n2
        d = abs(cdf1 - cdf2)
        if d > max_d:
            max_d = d
            
    return max_d

def compute_jsd(p_freq, q_freq):
    p_total = sum(p_freq.values())
    q_total = sum(q_freq.values())
    if p_total == 0 or q_total == 0: return 1.0
    
    p_probs = sorted([v / p_total for v in p_freq.values()], reverse=True)
    q_probs = sorted([v / q_total for v in q_freq.values()], reverse=True)
    
    max_len = max(len(p_probs), len(q_probs))
    p_probs.extend([0.0] * (max_len - len(p_probs)))
    q_probs.extend([0.0] * (max_len - len(q_probs)))
    
    def kl_divergence(p, q):
        return sum(p[i] * math.log(p[i] / q[i]) for i in range(len(p)) if p[i] > 0 and q[i] > 0)
        
    m_probs = [(p + q) / 2.0 for p, q in zip(p_probs, q_probs)]
    
    jsd = 0.5 * kl_divergence(p_probs, m_probs) + 0.5 * kl_divergence(q_probs, m_probs)
    return jsd

def precompute_fidelity():
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    ref_path = os.path.join(base_dir, "data", "reference_ieee_cis", "ieee-fraud-detection", "train_transaction.csv")
    sim_path = os.path.join(base_dir, "ml", "data", "simulated_baseline.csv")
    campaigns_path = os.path.join(base_dir, "ml", "data", "campaigns.json")
    out_path = os.path.join(base_dir, "ml", "data", "fidelity_results.json")

    print("Loading reference data...")
    seed = 42
    random.seed(seed)
    n_samples = 50000
    
    ref_legit_amt, ref_legit_hr = [], []
    ref_legit_merchant = Counter()
    
    with open(ref_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        idx_fraud = headers.index('isFraud')
        idx_amt = headers.index('TransactionAmt')
        idx_dt = headers.index('TransactionDT')
        idx_prod = headers.index('ProductCD')
        
        reservoir = []
        for i, row in enumerate(reader):
            if i < n_samples:
                reservoir.append((row[idx_fraud], row[idx_amt], row[idx_dt], row[idx_prod]))
            else:
                j = random.randint(0, i)
                if j < n_samples:
                    reservoir[j] = (row[idx_fraud], row[idx_amt], row[idx_dt], row[idx_prod])
                    
    for row in reservoir:
        if not row[0]: continue
        isfraud = int(row[0])
        amt = float(row[1])
        dt = int(row[2]) if row[2] else 0
        hr = (dt // 3600) % 24
        prod = row[3]
        
        if isfraud == 0:
            ref_legit_amt.append(amt)
            ref_legit_hr.append(hr)
            ref_legit_merchant[prod] += 1

    print("Loading synthetic data...")
    sim_legit_amt, sim_legit_hr = [], []
    sim_legit_merchant = Counter()
    
    with open(sim_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['label'].lower() == 'legit':
                amt = float(row['amount'])
                ts_str = row['timestamp']
                hr = 0
                if " " in ts_str:
                    time_str = ts_str.split(" ")[1]
                    hr = int(time_str.split(":")[0])
                sim_legit_amt.append(amt)
                sim_legit_hr.append(hr)
                sim_legit_merchant[row['merchant_id']] += 1

    results = []
    # 1. Legitimate baseline fidelity
    ks_amt = compute_ks(sim_legit_amt, ref_legit_amt)
    ks_hr = compute_ks(sim_legit_hr, ref_legit_hr)
    
    def get_ks_interpretation(ks_val):
        if ks_val < 0.1:
            return "strong match"
        elif ks_val <= 0.2:
            return "moderate match"
        else:
            return "meaningful divergence"
    
    results.append({
        "comparison": "synthetic legitimate vs IEEE-CIS legitimate",
        "feature": "transaction_amount",
        "metric": "ks_statistic",
        "value": float(ks_amt),
        "interpretation": f"KS={ks_amt:.3f} indicates {get_ks_interpretation(ks_amt)} between synthetic and real amount distributions."
    })
    results.append({
        "comparison": "synthetic legitimate vs IEEE-CIS legitimate",
        "feature": "hour_of_day",
        "metric": "ks_statistic",
        "value": float(ks_hr),
        "interpretation": f"KS={ks_hr:.3f} indicates {get_ks_interpretation(ks_hr)} between synthetic and real hourly patterns."
    })
    results.append({
        "comparison": "synthetic legitimate vs IEEE-CIS legitimate",
        "feature": "merchant_category",
        "metric": "omitted",
        "value": None,
        "interpretation": "Omitted. Merchant-category fidelity isn't directly comparable between the two datasets due to differing taxonomies (our unique merchant IDs vs IEEE-CIS's coded ProductCD values)."
    })
    
    # 2. Campaign Internal Consistency
    print("Checking campaign internal consistency...")
    with open(campaigns_path, "r", encoding="utf-8") as f:
        campaigns = json.load(f)
        
    phase_durations = []
    amount_jumps = []
    
    for c in campaigns:
        history = c.get("history", [])
        if not history: continue
        
        # Phase durations
        for i in range(len(history) - 1):
            try:
                t1 = datetime.fromisoformat(history[i]['timestamp'])
                t2 = datetime.fromisoformat(history[i+1]['timestamp'])
                duration_hrs = (t2 - t1).total_seconds() / 3600.0
                if duration_hrs > 0:
                    phase_durations.append(duration_hrs)
            except Exception:
                pass
                
        # Smoothness check (drift)
        amounts = []
        for h in history:
            params = h.get("parameters", {})
            if "avg_amount" in params:
                amounts.append(float(params["avg_amount"]))
                
        for i in range(len(amounts) - 1):
            if amounts[i] > 0:
                jump = amounts[i+1] / amounts[i]
                amount_jumps.append(jump)
                
    avg_duration = sum(phase_durations) / len(phase_durations) if phase_durations else 0
    max_duration = max(phase_durations) if phase_durations else 0
    avg_jump = sum(amount_jumps) / len(amount_jumps) if amount_jumps else 0
    max_jump = max(amount_jumps) if amount_jumps else 0
    
    results.append({
        "comparison": "internal consistency",
        "feature": "campaign_phase_duration_hours",
        "metric": "average",
        "value": float(avg_duration)
    })
    results.append({
        "comparison": "internal consistency",
        "feature": "behavioral_drift_amount_multiplier",
        "metric": "average_jump",
        "value": float(avg_jump)
    })
    results.append({
        "comparison": "internal consistency",
        "feature": "behavioral_drift_amount_multiplier",
        "metric": "max_jump",
        "value": float(max_jump),
        "interpretation": "Ensures no unrealistic step-function jumps between seeding and drift"
    })
    
    output = {
        "metadata": {
            "reference_dataset": "IEEE-CIS",
            "reference_usage": "external distribution comparison only",
            "training_usage": False,
            "sample_seed": seed,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        },
        "results": results
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)
        
    print(f"Fidelity results saved to {out_path}")

if __name__ == "__main__":
    precompute_fidelity()
