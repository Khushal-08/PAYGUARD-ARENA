import pandas as pd
import numpy as np

df = pd.read_csv("ml/data/simulated_baseline.csv")

print("="*40)
print("BASELINE SANITY CHECK")
print("="*40)
print(f"Total Transactions: {len(df):,}")

# Transactions per user
user_counts = df['account_id'].value_counts()
print(f"\nTransactions per account:")
print(f"  Min: {user_counts.min()}")
print(f"  Median: {user_counts.median()}")
print(f"  Max: {user_counts.max()}")

# Amount stats
amt = df['amount']
print("\nAmount Distribution:")
print(f"  Mean:   ${amt.mean():.2f}")
print(f"  Median: ${amt.median():.2f}")
print(f"  StdDev: ${amt.std():.2f}")
print(f"  25th %: ${amt.quantile(0.25):.2f}")
print(f"  75th %: ${amt.quantile(0.75):.2f}")
print(f"  95th %: ${amt.quantile(0.95):.2f}")

# Hour-of-day histogram
df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
hour_counts = df['hour'].value_counts().sort_index()

print("\nHour of Day Histogram:")
max_count = hour_counts.max()
for h in range(24):
    count = hour_counts.get(h, 0)
    if max_count > 0:
        bar = '*' * int((count / max_count) * 40)
    else:
        bar = ''
    print(f"{h:02d}: {bar} ({count})")
