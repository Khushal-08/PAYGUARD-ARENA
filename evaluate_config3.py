import os
import json
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc
from xgboost import XGBClassifier
from ml.features.entity_aggregates import engineer_all_entity_features

def evaluate_predictions(y_true, y_pred):
    auc_score = roc_auc_score(y_true, y_pred)
    precision, recall, _ = precision_recall_curve(y_true, y_pred)
    pr_auc = auc(recall, precision)
    return {"AUC": auc_score, "PR_AUC": pr_auc}

def check_time_consistency_c3(df: pd.DataFrame, target_col: str, feature_cols: list, time_col: str = 'timestamp'):
    df = df.sort_values(time_col).reset_index(drop=True)
    split_idx = len(df) // 2
    train_df = df.iloc[:split_idx]
    val_df = df.iloc[split_idx:]
    y_train = train_df[target_col]
    y_val = val_df[target_col]
    
    scale_weight = (len(y_train) - y_train.sum()) / max(1, y_train.sum())
    
    results = []
    for col in feature_cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
            
        X_train = train_df[[col]].fillna(0)
        X_val = val_df[[col]].fillna(0)
        
        if len(y_train.unique()) < 2 or len(y_val.unique()) < 2:
            continue
            
        # Using Config 3 capacity
        clf = XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1, 
            scale_pos_weight=scale_weight, random_state=42,
            eval_metric='logloss'
        )
        clf.fit(X_train, y_train)
        
        train_preds = clf.predict_proba(X_train)[:, 1]
        val_preds = clf.predict_proba(X_val)[:, 1]
        
        train_auc = roc_auc_score(y_train, train_preds)
        val_auc = roc_auc_score(y_val, val_preds)
        
        is_consistent = not (val_auc < train_auc - 0.1 or val_auc < 0.5)
        results.append({
            'feature': col,
            'train_auc': train_auc,
            'val_auc': val_auc,
            'is_time_consistent': is_consistent,
            'reason': 'AUC Collapse' if not is_consistent else 'Stable'
        })
    return pd.DataFrame(results)

def generate_multi_temporal_splits(df: pd.DataFrame, time_col: str = 'timestamp'):
    df = df.sort_values(time_col).reset_index(drop=True)
    df['month'] = (df[time_col] - df[time_col].min()).dt.days // 30
    max_month = df['month'].max()
    
    splits = []
    
    # Strategy 1: Standard
    split_idx = len(df) // 2
    splits.append({
        'name': 'standard_half_split',
        'train': df.iloc[:split_idx],
        'val': df.iloc[split_idx:]
    })
    
    # Strategy 2: Gap
    if max_month >= 2:
        splits.append({
            'name': 'train_0_skip_1_predict_2',
            'train': df[df['month'] == 0],
            'val': df[df['month'] >= 2]
        })
        
    # Strategy 3: Train 0+1, Predict 2
    if max_month >= 2:
        splits.append({
            'name': 'train_0_1_predict_2',
            'train': df[df['month'] <= 1],
            'val': df[df['month'] >= 2]
        })
    return splits

def evaluate_robustness_c3(df: pd.DataFrame, target_col: str, feature_cols: list):
    splits = generate_multi_temporal_splits(df)
    results = []
    
    for split in splits:
        train_df = split['train']
        val_df = split['val']
        
        if len(train_df[target_col].unique()) < 2 or len(val_df[target_col].unique()) < 2:
            continue
            
        X_train = train_df[feature_cols].fillna(0)
        y_train = train_df[target_col]
        X_val = val_df[feature_cols].fillna(0)
        y_val = val_df[target_col]
        
        scale_weight = (len(y_train) - y_train.sum()) / max(1, y_train.sum())
        
        # Using Config 3 capacity
        clf = XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1, 
            scale_pos_weight=scale_weight, random_state=42,
            eval_metric='logloss'
        )
        clf.fit(X_train, y_train)
        
        train_preds = clf.predict_proba(X_train)[:, 1]
        val_preds = clf.predict_proba(X_val)[:, 1]
        
        train_res = evaluate_predictions(y_train, train_preds)
        val_res = evaluate_predictions(y_val, val_preds)
        
        results.append({
            'split_name': split['name'],
            'train_auc': train_res['AUC'],
            'train_pr_auc': train_res['PR_AUC'],
            'val_auc': val_res['AUC'],
            'val_pr_auc': val_res['PR_AUC']
        })
    
    return pd.DataFrame(results)

def main():
    print("Loading data...")
    df = pd.read_csv("ml/data/simulated_baseline.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    print("Engineering features...")
    df = engineer_all_entity_features(df)
    df['hour_of_day'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_fraud'] = (df['label'] == 'Fraud').astype(int)
    
    raw_features = ['amount', 'hour_of_day', 'day_of_week']
    agg_features = [
        'account_time_since_last_txn', 'is_new_account', 'account_txns_24h', 'account_txns_7d',
        'device_txns_7d', 'is_familiar_merchant'
    ]
    all_features = raw_features + agg_features
    
    print("\n--- 1. check_time_consistency() with Config 3 capacity ---")
    consistency_df = check_time_consistency_c3(df, 'is_fraud', all_features)
    print(consistency_df.to_string())
    
    # Dump time consistency results to JSON
    consistency_json_path = "ml/data/time_consistency_results.json"
    consistency_df.to_json(consistency_json_path, orient='records', indent=2)
    print(f"Saved time consistency results to {consistency_json_path}")
    
    print("\n--- 2. evaluate_robustness_across_splits() with Config 3 capacity ---")
    robustness_df = evaluate_robustness_c3(df, 'is_fraud', all_features)
    print(robustness_df.to_string())

if __name__ == "__main__":
    main()
