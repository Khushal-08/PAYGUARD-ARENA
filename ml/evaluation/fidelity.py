import os
import csv
import json
import random
import bisect
from datetime import datetime

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
    
    with open(ref_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        idx_fraud = headers.index('isFraud')
        idx_amt = headers.index('TransactionAmt')
        idx_dt = headers.index('TransactionDT')
        
        reservoir = []
        for i, row in enumerate(reader):
            if i < n_samples:
                reservoir.append((row[idx_fraud], row[idx_amt], row[idx_dt]))
            else:
                j = random.randint(0, i)
                if j < n_samples:
                    reservoir[j] = (row[idx_fraud], row[idx_amt], row[idx_dt])
        
    ref_legit_amt, ref_legit_hr = [], []
    ref_fraud_amt, ref_fraud_hr = [], []
    
    for row in reservoir:
        if not row[0]: continue
        isfraud = int(row[0])
        amt = float(row[1])
        dt = int(row[2]) if row[2] else 0
        hr = (dt // 3600) % 24
        
        if isfraud == 0:
            ref_legit_amt.append(amt)
            ref_legit_hr.append(hr)
        else:
            ref_fraud_amt.append(amt)
            ref_fraud_hr.append(hr)

    print("Loading synthetic data...")
    with open(campaigns_path, "r", encoding="utf-8") as f:
        campaigns = json.load(f)
    attack_map = {c['campaign_id']: c['attack_type'] for c in campaigns}
    
    sim_legit_amt, sim_legit_hr = [], []
    sim_attacks_amt = {"Synthetic Identity": [], "Account Takeover": [], "GenAI Social Engineering": []}
    sim_attacks_hr = {"Synthetic Identity": [], "Account Takeover": [], "GenAI Social Engineering": []}
    
    with open(sim_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            amt = float(row['amount'])
            ts_str = row['timestamp']
            hr = 0
            if " " in ts_str:
                time_str = ts_str.split(" ")[1]
                hr = int(time_str.split(":")[0])
                
            label = row['label'].lower()
            if label == 'legit':
                sim_legit_amt.append(amt)
                sim_legit_hr.append(hr)
            else:
                cid = row.get('campaign_id')
                if cid and cid in attack_map:
                    atype = attack_map[cid]
                    if atype in sim_attacks_amt:
                        sim_attacks_amt[atype].append(amt)
                        sim_attacks_hr[atype].append(hr)
                        
    results = []
    def add_comparison(attack_type, comp_name, feature_name, sim_vals, ref_vals):
        if len(sim_vals) == 0 or len(ref_vals) == 0:
            return
        ks_stat = compute_ks(sim_vals, ref_vals)
        results.append({
            "attack_type": attack_type,
            "comparison": comp_name,
            "feature": feature_name,
            "metric": "ks_statistic",
            "value": float(ks_stat),
            "reference_sample_size": len(ref_vals),
            "synthetic_sample_size": len(sim_vals)
        })
        
    # A. Legitimate baseline
    add_comparison("Legitimate Baseline", "synthetic legitimate vs IEEE-CIS legitimate", "transaction_amount", sim_legit_amt, ref_legit_amt)
    add_comparison("Legitimate Baseline", "synthetic legitimate vs IEEE-CIS legitimate", "transaction_hour", sim_legit_hr, ref_legit_hr)
    
    # B, C, D. Attacks
    for atype in ["Synthetic Identity", "Account Takeover", "GenAI Social Engineering"]:
        add_comparison(atype, f"synthetic {atype} fraud vs IEEE-CIS fraud", "transaction_amount", sim_attacks_amt[atype], ref_fraud_amt)
        add_comparison(atype, f"synthetic {atype} fraud vs IEEE-CIS fraud", "transaction_hour", sim_attacks_hr[atype], ref_fraud_hr)
        
    output = {
        "metadata": {
            "reference_dataset": "IEEE-CIS",
            "reference_usage": "external distribution comparison only",
            "training_usage": False,
            "sample_seed": seed,
            "sample_size": len(reservoir),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "method": "KS",
            "interpretation": "A KS statistic measures the maximum difference between two empirical distributions. Smaller values indicate greater distributional similarity. Lower KS indicates greater distributional similarity for this feature."
        },
        "results": results
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)
        
    print(f"Fidelity results saved to {out_path}")

if __name__ == "__main__":
    precompute_fidelity()
