import pandas as pd
from typing import List, Tuple, Dict
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

def generate_multi_temporal_splits(df: pd.DataFrame, time_col: str = 'timestamp') -> List[Dict[str, pd.DataFrame]]:
    """
    Generates multiple diverse validation splits to prevent overfitting to a single temporal holdout.
    Modeled after the IEEE-CIS 1st place solution's validation strategy.
    """
    df = df.sort_values(time_col).reset_index(drop=True)
    
    # We will assume a 3 month total duration (approx 90 days). 
    # Create month identifiers
    df['month'] = (df[time_col] - df[time_col].min()).dt.days // 30
    max_month = df['month'].max()
    
    splits = []
    
    # Strategy 1: Train on first half, Predict on second half (Standard chronological)
    split_idx = len(df) // 2
    splits.append({
        'name': 'standard_half_split',
        'train': df.iloc[:split_idx],
        'val': df.iloc[split_idx:]
    })
    
    # Strategy 2: Train on Month 0, Skip Month 1, Predict Month 2 (Gap split)
    if max_month >= 2:
        splits.append({
            'name': 'train_0_skip_1_predict_2',
            'train': df[df['month'] == 0],
            'val': df[df['month'] >= 2]
        })
        
    # Strategy 3: Group K-Fold on Time (e.g. predicting middle month from surrounding, 
    # though technically lookahead, sometimes used for feature stability checks. 
    # We will stick to strict chronological for fraud: Train 0+1, Predict 2)
    if max_month >= 2:
        splits.append({
            'name': 'train_0_1_predict_2',
            'train': df[df['month'] <= 1],
            'val': df[df['month'] >= 2]
        })
        
    return splits

def evaluate_robustness_across_splits(df: pd.DataFrame, target_col: str, feature_cols: list) -> pd.DataFrame:
    """
    Trains a baseline model on multiple splits and compares performance.
    If metrics disagree significantly, it warns against trusting the baseline.
    """
    splits = generate_multi_temporal_splits(df)
    results = []
    
    for split in splits:
        train_df = split['train']
        val_df = split['val']
        
        # We need both classes to compute AUC. 
        if len(train_df[target_col].unique()) < 2 or len(val_df[target_col].unique()) < 2:
            continue
            
        X_train = train_df[feature_cols].fillna(0)
        y_train = train_df[target_col]
        X_val = val_df[feature_cols].fillna(0)
        y_val = val_df[target_col]
        
        clf = XGBClassifier(n_estimators=50, max_depth=4, eval_metric='auc', random_state=42)
        clf.fit(X_train, y_train)
        
        val_preds = clf.predict_proba(X_val)[:, 1]
        val_auc = roc_auc_score(y_val, val_preds)
        
        results.append({
            'split_name': split['name'],
            'val_auc': val_auc
        })
        
    res_df = pd.DataFrame(results)
    if len(res_df) > 1:
        auc_variance = res_df['val_auc'].max() - res_df['val_auc'].min()
        res_df['is_robust'] = auc_variance < 0.05
    
    return res_df
