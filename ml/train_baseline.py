import os
import json
import pandas as pd
import numpy as np
import xgboost as xgb
import pickle
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc
from ml.features.entity_aggregates import engineer_all_entity_features

def evaluate_predictions(y_true, y_pred, name="Model"):
    auc_score = roc_auc_score(y_true, y_pred)
    precision, recall, _ = precision_recall_curve(y_true, y_pred)
    pr_auc = auc(recall, precision)
    return {"AUC": auc_score, "PR_AUC": pr_auc}

def split_chronological(df: pd.DataFrame):
    """60/20/20 split based on time."""
    df = df.sort_values('timestamp')
    n = len(df)
    train_end = int(n * 0.6)
    val_end = int(n * 0.8)
    
    train = df.iloc[:train_end]
    val = df.iloc[train_end:val_end]
    test = df.iloc[val_end:]
    return train, val, test

def main():
    import random
    random.seed(42)
    np.random.seed(42)
    print("Loading simulated baseline data...")
    df = pd.read_csv("ml/data/simulated_baseline.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 1. Feature Engineering
    print("Engineering features...")
    df = engineer_all_entity_features(df)
    
    # Raw features
    df['hour_of_day'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    
    # Labels
    df['is_fraud'] = (df['label'] == 'Fraud').astype(int)
    
    # 2. Chronological Split
    train, val, test = split_chronological(df)
    print(f"Train: {len(train)} | Val: {len(val)} | Test: {len(test)}")
    
    y_train = train['is_fraud']
    y_val = val['is_fraud']
    y_test = test['is_fraud']
    
    results = {}
    
    # ==========================================
    # Config 1: Rules-Only (No ML)
    # ==========================================
    print("\n--- Training Config 1: Rules-Only ---")
    # Simple rule: High amount OR high velocity
    # We'll normalize to a 0-1 score
    def rule_based_score(data):
        score_amount = np.clip(data['amount'] / 1000.0, 0, 1)
        score_velocity = np.clip(data['account_txns_24h'] / 10.0, 0, 1)
        return np.clip(score_amount * 0.5 + score_velocity * 0.5, 0, 1)
        
    y_pred_test_c1 = rule_based_score(test)
    results['Config 1 (Rules)'] = evaluate_predictions(y_test, y_pred_test_c1)
    
    # ==========================================
    # Config 2: XGBoost (Raw Features Only)
    # ==========================================
    print("--- Training Config 2: XGBoost (Raw Features) ---")
    raw_features = ['amount', 'hour_of_day', 'day_of_week']
    X_train_c2 = train[raw_features]
    X_val_c2 = val[raw_features]
    X_test_c2 = test[raw_features]
    
    scale_weight = (len(y_train) - y_train.sum()) / max(1, y_train.sum())
    
    model_c2 = xgb.XGBClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.1, 
        scale_pos_weight=scale_weight, random_state=42,
        eval_metric='logloss', early_stopping_rounds=10
    )
    model_c2.fit(X_train_c2, y_train, eval_set=[(X_val_c2, y_val)], verbose=False)
    
    y_pred_test_c2 = model_c2.predict_proba(X_test_c2)[:, 1]
    results['Config 2 (XGB Raw)'] = evaluate_predictions(y_test, y_pred_test_c2)
    
    # ==========================================
    # Config 3: XGBoost (Raw + Entity Aggregates)
    # ==========================================
    print("--- Training Config 3: XGBoost (Raw + Aggregates) ---")
    agg_features = [
        'account_time_since_last_txn', 'is_new_account', 'account_txns_24h', 'account_txns_7d',
        'device_txns_7d', 'is_familiar_merchant'
    ] # Note: device_age_days is excluded due to time-consistency failure
    all_features = raw_features + agg_features
    X_train_c3 = train[all_features]
    X_val_c3 = val[all_features]
    X_test_c3 = test[all_features]
    
    model_c3 = xgb.XGBClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.1, 
        scale_pos_weight=scale_weight, random_state=42,
        eval_metric='logloss', early_stopping_rounds=10
    )
    model_c3.fit(X_train_c3, y_train, eval_set=[(X_val_c3, y_val)], verbose=False)
    
    y_pred_test_c3 = model_c3.predict_proba(X_test_c3)[:, 1]
    results['Config 3 (XGB + Agg)'] = evaluate_predictions(y_test, y_pred_test_c3)
    
    # ==========================================
    # Evaluation Comparison
    # ==========================================
    print("\n========================================")
    print("BASELINE LADDER EVALUATION (TEST SET)")
    print("========================================")
    print(f"{'Model Configuration':<28} | {'AUC':<7} | {'PR-AUC':<7}")
    print("-" * 48)
    for name, metrics in results.items():
        print(f"{name:<28} | {metrics['AUC']:.4f} | {metrics['PR_AUC']:.4f}")
        
    # Print top features for Config 3
    print("\nConfig 3 Top Features (Gain):")
    importance = model_c3.get_booster().get_score(importance_type='gain')
    sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    for feat, gain in sorted_imp[:5]:
        print(f"  {feat}: {gain:.2f}")

    # Save Config 3 as Round 0
    os.makedirs("ml/models", exist_ok=True)
    model_path = "ml/models/xgboost_baseline_round_0.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model_c3, f)
    print(f"\nSaved Config 3 model to {model_path}")
    
    # Dump results to JSON
    json_results = []
    for name, metrics in results.items():
        json_results.append({
            "config": name,
            "auc": metrics['AUC'],
            "pr_auc": metrics['PR_AUC']
        })
    json_path = "ml/data/baseline_results.json"
    with open(json_path, "w") as f:
        json.dump(json_results, f, indent=2)
    print(f"Saved baseline results to {json_path}")

if __name__ == "__main__":
    main()
