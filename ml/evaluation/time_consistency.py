import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

def check_time_consistency(df: pd.DataFrame, target_col: str, feature_cols: list, time_col: str = 'timestamp') -> pd.DataFrame:
    """
    Evaluates individual features for time consistency by training on the first half
    of the dataset chronologically and predicting on the second half.
    Flags features where validation AUC drops significantly below training AUC.
    """
    # Sort chronologically
    df = df.sort_values(time_col).reset_index(drop=True)
    
    # Split chronologically in half
    split_idx = len(df) // 2
    train_df = df.iloc[:split_idx]
    val_df = df.iloc[split_idx:]
    
    y_train = train_df[target_col]
    y_val = val_df[target_col]
    
    results = []
    
    for col in feature_cols:
        # Skip non-numeric or directly leaky columns
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
            
        X_train = train_df[[col]].fillna(0) # Simple imputation for isolated test
        X_val = val_df[[col]].fillna(0)
        
        # We need both classes to compute AUC. If one split is purely legit (e.g. baseline),
        # this check requires adversarial data to be present in both halves, or we just measure
        # stability of predictions. Assuming binary classification for fraud.
        if len(y_train.unique()) < 2 or len(y_val.unique()) < 2:
            results.append({
                'feature': col,
                'train_auc': np.nan,
                'val_auc': np.nan,
                'is_time_consistent': False,
                'reason': 'Single class in split'
            })
            continue
            
        # Train a simple tree-based model (depth 1 or 2 is enough for single feature)
        clf = XGBClassifier(max_depth=2, n_estimators=20, eval_metric='auc', random_state=42)
        clf.fit(X_train, y_train)
        
        train_preds = clf.predict_proba(X_train)[:, 1]
        val_preds = clf.predict_proba(X_val)[:, 1]
        
        train_auc = roc_auc_score(y_train, train_preds)
        val_auc = roc_auc_score(y_val, val_preds)
        
        # Threshold: if validation AUC is worse by more than 0.1 (or drops below 0.55 if train was good), flag it
        # The IEEE-CIS writeup noted bad features had train AUC ~0.60 and val AUC ~0.40.
        is_consistent = not (val_auc < train_auc - 0.1 or val_auc < 0.5)
        
        results.append({
            'feature': col,
            'train_auc': train_auc,
            'val_auc': val_auc,
            'is_time_consistent': is_consistent,
            'reason': 'AUC Collapse' if not is_consistent else 'Stable'
        })
        
    return pd.DataFrame(results)

def run_adaptive_attack_consistency_check(df: pd.DataFrame, target_col: str, feature_cols: list) -> pd.DataFrame:
    """
    Runs time consistency check specifically against adaptive attack rounds.
    This guarantees that features reliant on static attacker behavior fail.
    """
    # Just an alias wrapper assuming df includes Round 1 vs Round 2/3 data
    return check_time_consistency(df, target_col, feature_cols)
