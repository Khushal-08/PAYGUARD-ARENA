import pandas as pd
import numpy as np

def compute_account_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes per-account transaction frequency and recency.
    Assumes df is sorted by timestamp chronologically.
    """
    # Ensure datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calculate time since last transaction for the account
    # Leave as np.nan for the very first transaction so XGBoost handles it properly
    df['account_time_since_last_txn'] = df.groupby('account_id')['timestamp'].diff().dt.total_seconds()
    
    # Explicitly flag if this is the first transaction for the account
    df['is_new_account'] = df['account_time_since_last_txn'].isna().astype(int)
    
    # Calculate rolling frequency strictly prior to current transaction to avoid leakage
    # Using rolling windows requires an index on timestamp
    df = df.set_index('timestamp')
    df['account_txns_24h'] = df.groupby('account_id')['txn_id'].transform(lambda x: x.rolling('24h', closed='left').count()).fillna(0)
    df['account_txns_7d'] = df.groupby('account_id')['txn_id'].transform(lambda x: x.rolling('7d', closed='left').count()).fillna(0)
    df = df.reset_index()
    
    return df

def compute_device_aggregates(df: pd.DataFrame, devices_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Computes per-device trust-score history and first-seen recency.
    """
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Device first-seen recency
    df['device_first_seen_recency'] = df.groupby('device_id')['timestamp'].transform('min')
    df['device_age_days'] = (df['timestamp'] - df['device_first_seen_recency']).dt.total_seconds() / 86400.0
    
    # Trust score history is a proxy if we assume trust score changes are logged or recomputed.
    # For now, we compute transaction frequency on the device as a behavioral feature.
    df = df.set_index('timestamp')
    df['device_txns_7d'] = df.groupby('device_id')['txn_id'].transform(lambda x: x.rolling('7d', closed='left').count()).fillna(0)
    df = df.reset_index()
    
    return df

def compute_merchant_familiarity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes per-merchant familiarity for an account.
    (has this account transacted with this merchant before, and how many times)
    """
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Cumulative count of transactions between this account and this merchant (before the current transaction)
    df['merchant_account_cumulative_txns'] = df.groupby(['account_id', 'merchant_id']).cumcount()
    
    # Binary flag for familiarity
    df['is_familiar_merchant'] = (df['merchant_account_cumulative_txns'] > 0).astype(int)
    
    return df

def engineer_all_entity_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pipeline to apply all entity aggregates.
    """
    # Sort chronologically to prevent temporal leakage in cumulative ops
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    df = compute_account_aggregates(df)
    df = compute_device_aggregates(df)
    df = compute_merchant_familiarity(df)
    
    return df
