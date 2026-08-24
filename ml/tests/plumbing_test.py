import pandas as pd
import numpy as np
import sys
import os

# Ensure we can import from ml
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ml.features.entity_aggregates import engineer_all_entity_features
from ml.evaluation.time_consistency import check_time_consistency
from ml.evaluation.validation_splits import evaluate_robustness_across_splits

def run_tests():
    print("Loading baseline data...")
    df = pd.read_csv("ml/data/simulated_baseline.csv")
    
    print("\n--- Running Entity Aggregates ---")
    df = engineer_all_entity_features(df)
    new_cols = [c for c in df.columns if 'account_' in c or 'device_' in c or 'merchant_' in c]
    print(f"Added columns: {new_cols}")

    # Use the real 'is_fraud' column from the data (based on label='Fraud')
    if 'label' in df.columns:
        df['is_fraud'] = (df['label'] == 'Fraud').astype(int)
    else:
        df['is_fraud'] = 0


    feature_cols = ['amount', 'account_time_since_last_txn', 'account_txns_24h', 'device_txns_7d']

    print("\n--- Running Time Consistency Check ---")
    consistency_res = check_time_consistency(df, target_col='is_fraud', feature_cols=feature_cols)
    print(consistency_res.to_string())

    print("\n--- Running Multi-Split Robustness Check ---")
    robustness_res = evaluate_robustness_across_splits(df, target_col='is_fraud', feature_cols=feature_cols)
    print(robustness_res.to_string())
    print("\nPlumbing tests finished successfully.")

if __name__ == "__main__":
    run_tests()
