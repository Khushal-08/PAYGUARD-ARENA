import pandas as pd
import numpy as np

def main():
    print("Loading data...")
    df = pd.read_csv("ml/data/simulated_baseline.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Simulate feature engineering before filling NAs
    df['account_time_since_last_txn_raw'] = df.sort_values('timestamp').groupby('account_id')['timestamp'].diff().dt.total_seconds()
    
    # Identify new vs day-0 accounts
    # Day 0 is around 2026-01-01 00:00:00
    start_time = df['timestamp'].min()
    # Accounts created on day 0
    day0_users = df.groupby('account_id')['timestamp'].min()
    day0_users = day0_users[day0_users <= start_time + pd.Timedelta(days=1)].index
    
    df['is_day0_user'] = df['account_id'].isin(day0_users)
    
    day0_df = df[df['is_day0_user']]
    new_df = df[~df['is_day0_user']]
    
    print("\nMissing Value Rates (account_time_since_last_txn_raw):")
    print(f"Overall: {df['account_time_since_last_txn_raw'].isna().mean():.4f}")
    print(f"Day-0 Users: {day0_df['account_time_since_last_txn_raw'].isna().mean():.4f}")
    print(f"Newly Onboarded Users: {new_df['account_time_since_last_txn_raw'].isna().mean():.4f}")
    
    print("\nHow it was filled previously in entity_aggregates.py:")
    print("df['account_time_since_last_txn'] = df.groupby('account_id')['timestamp'].diff().dt.total_seconds().fillna(-1)")
    print("This encoded 'first transaction' as -1 seconds (instantaneous), destroying the feature.")

if __name__ == "__main__":
    main()
