import pandas as pd

df = pd.read_csv("ml/data/simulated_baseline.csv")
legit = df[df['label'] == 'Legit']
fraud = df[df['label'] == 'Fraud']

print("========================================")
print("FRAUD VS LEGITIMATE SUMMARY STATS")
print("========================================")
print(f"Total Legit Txns: {len(legit):,}")
print(f"Total Fraud Txns: {len(fraud):,}")

print("\nAmount Distribution:")
print("       | Legit | Fraud")
print("-----------------------")
print(f"Mean   | ${legit['amount'].mean():.2f} | ${fraud['amount'].mean():.2f}")
print(f"Median | ${legit['amount'].median():.2f} | ${fraud['amount'].median():.2f}")
print(f"Max    | ${legit['amount'].max():.2f} | ${fraud['amount'].max():.2f}")

print("\nHour of Day Distribution:")
legit_hour = pd.to_datetime(legit['timestamp']).dt.hour.value_counts(normalize=True).sort_index()
fraud_hour = pd.to_datetime(fraud['timestamp']).dt.hour.value_counts(normalize=True).sort_index()

print("Hour | Legit % | Fraud %")
print("------------------------")
for h in range(24):
    l_pct = legit_hour.get(h, 0) * 100
    f_pct = fraud_hour.get(h, 0) * 100
    print(f"{h:02d}   | {l_pct:5.1f}% | {f_pct:5.1f}%")

print("\n========================================")
print("CAMPAIGN PARAMETER DIVERSITY (400 Campaigns)")
print("========================================")

import json
from datetime import datetime

with open("ml/data/campaigns.json") as f:
    campaigns = json.load(f)

seed_counts = []
seed_amts = []
drift_counts = []
drift_amts = []
durations_days = []
strategies = []

for c in campaigns:
    hist = c.get("history", [])
    if not hist: continue
    
    start_t = datetime.fromisoformat(hist[0]["timestamp"])
    end_t = datetime.fromisoformat(hist[-1]["timestamp"])
    durations_days.append((end_t - start_t).total_seconds() / 86400.0)
    
    for action in hist:
        if action["phase"] == "normal_seeding":
            seed_counts.append(action["parameters"]["count"])
            seed_amts.append(action["parameters"]["avg_amount"])
        elif action["phase"] == "gradual_drift":
            drift_counts.append(action["parameters"]["count"])
            drift_amts.append(action["parameters"]["avg_amount"])
        elif action["phase"] == "fraud_attempt":
            strategies.append(action["parameters"]["timing_strategy"])

print("Metric                  | Min    | Median | Max")
print("-------------------------------------------------")
print(f"Duration (Days)         | {min(durations_days):<6.1f} | {pd.Series(durations_days).median():<6.1f} | {max(durations_days):<6.1f}")
print(f"Seed Txn Count          | {min(seed_counts):<6} | {pd.Series(seed_counts).median():<6.0f} | {max(seed_counts):<6}")
print(f"Seed Avg Amount ($)     | {min(seed_amts):<6.1f} | {pd.Series(seed_amts).median():<6.1f} | {max(seed_amts):<6.1f}")
print(f"Drift Txn Count         | {min(drift_counts):<6} | {pd.Series(drift_counts).median():<6.0f} | {max(drift_counts):<6}")
print(f"Drift Avg Amount ($)    | {min(drift_amts):<6.1f} | {pd.Series(drift_amts).median():<6.1f} | {max(drift_amts):<6.1f}")

from collections import Counter
print(f"\nTiming Strategies: {dict(Counter(strategies))}")

