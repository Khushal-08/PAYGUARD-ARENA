import os
import json
import pickle
import pandas as pd
import numpy as np
import shap
from datetime import datetime, timedelta
import random

from simulation.state.environment import PaymentEnvironment
from simulation.state.baseline_generator import LegitimateTrafficGenerator
from simulation.attacks.synthetic_identity import SyntheticIdentityAgent
from simulation.attacks.account_takeover import AccountTakeoverAgent
from simulation.attacks.genai_social_engineering import SocialEngineeringAgent

def default_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    from uuid import UUID
    if isinstance(obj, UUID):
        return str(obj)
    return str(obj)

def main():
    random.seed(42)
    np.random.seed(42)
    start_time = datetime(2026, 1, 1, 0, 0, 0)
    env = PaymentEnvironment(start_time=start_time)
    
    # Bootstrap world
    generator = LegitimateTrafficGenerator(env=env, num_users=50, num_merchants=20)
    generator.bootstrap_world()
    generator.generate_timeline(duration_days=30)
    
    # Load Model and Explainer
    model_path = "ml/models/xgboost_baseline_round_1.pkl"
    with open(model_path, "rb") as f:
        model = pickle.load(f)
        explainer = shap.TreeExplainer(model)
        
    features = [
        'amount', 'hour_of_day', 'day_of_week', 
        'account_time_since_last_txn', 'is_new_account', 'account_txns_24h', 
        'account_txns_7d', 'device_txns_7d', 'is_familiar_merchant'
    ]
        
    def get_shap(txn_obj):
        past_txns = [t for t in env.transactions if t.timestamp < txn_obj.timestamp]
        acc_txns = [t for t in past_txns if t.account_id == txn_obj.account_id]
        
        if acc_txns:
            account_time_since_last_txn = (txn_obj.timestamp - acc_txns[-1].timestamp).total_seconds()
            is_new_account = 0.0
        else:
            account_time_since_last_txn = np.nan
            is_new_account = 1.0
            
        acc_txns_24h = len([t for t in acc_txns if (txn_obj.timestamp - t.timestamp).total_seconds() <= 86400])
        acc_txns_7d = len([t for t in acc_txns if (txn_obj.timestamp - t.timestamp).total_seconds() <= 7*86400])
        
        dev_txns = [t for t in past_txns if t.device_id == txn_obj.device_id]
        device_txns_7d = len([t for t in dev_txns if (txn_obj.timestamp - t.timestamp).total_seconds() <= 7*86400])
        
        is_familiar_merchant = 1.0 if any(t.merchant_id == txn_obj.merchant_id for t in acc_txns) else 0.0
        
        row = {
            'amount': float(txn_obj.amount),
            'hour_of_day': float(txn_obj.timestamp.hour),
            'day_of_week': float(txn_obj.timestamp.weekday()),
            'account_time_since_last_txn': account_time_since_last_txn,
            'is_new_account': is_new_account,
            'account_txns_24h': float(acc_txns_24h),
            'account_txns_7d': float(acc_txns_7d),
            'device_txns_7d': float(device_txns_7d),
            'is_familiar_merchant': is_familiar_merchant
        }
        df = pd.DataFrame([row])
        shap_values = explainer.shap_values(df)
        if isinstance(shap_values, list):
            sv = shap_values[1][0]
        else:
            sv = shap_values[0]
        importances = list(zip(features, sv))
        importances.sort(key=lambda x: abs(x[1]), reverse=True)
        return [[feat, float(val)] for feat, val in importances[:3]]

    samples = []
    
    # Synthetic Identity
    si_agent = SyntheticIdentityAgent(env=env, round_id=1)
    for i in range(3):
        attack_start = start_time + timedelta(days=random.randint(1, 10))
        campaign = si_agent.execute_campaign(start_time=attack_start)
        c_dict = campaign.model_dump()
        txns = [t for t in env.transactions if t.campaign_id == campaign.campaign_id]
        if txns:
            c_dict['shap_explanation'] = get_shap(txns[-1])
        samples.append(c_dict)

    # Account Takeover
    ato_agent = AccountTakeoverAgent(env=env, round_id=1)
    valid_users = [u for u in env.users.values() if not u.is_synthetic]
    for i in range(3):
        user = random.choice(valid_users)
        account = next((a for a in env.accounts.values() if a.user_id == user.user_id), None)
        card = next((c for c in env.cards.values() if c.account_id == account.account_id), None) if account else None
        if account and card:
            attack_start = account.opened_at + timedelta(days=random.randint(2, 20))
            campaign = ato_agent.execute_campaign(start_time=attack_start, user=user, account=account, card=card)
            c_dict = campaign.model_dump()
            txns = [t for t in env.transactions if t.campaign_id == campaign.campaign_id]
            if txns:
                c_dict['shap_explanation'] = get_shap(txns[-1])
            samples.append(c_dict)
            
    # GenAI Social Engineering
    se_agent = SocialEngineeringAgent(env=env, round_id=1)
    for i in range(3):
        user = random.choice(valid_users)
        account = next((a for a in env.accounts.values() if a.user_id == user.user_id), None)
        card = next((c for c in env.cards.values() if c.account_id == account.account_id), None) if account else None
        if account and card:
            attack_start = account.opened_at + timedelta(days=random.randint(2, 20))
            campaign = se_agent.execute_campaign(start_time=attack_start, user=user, account=account, card=card)
            c_dict = campaign.model_dump()
            txns = [t for t in env.transactions if t.campaign_id == campaign.campaign_id]
            if txns:
                c_dict['shap_explanation'] = get_shap(txns[-1])
            samples.append(c_dict)

    out_path = "ml/data/campaign_samples.json"
    with open(out_path, "w") as f:
        json.dump(samples, f, default=default_serializer, indent=2)
    print(f"Saved {len(samples)} campaigns to {out_path}")

if __name__ == "__main__":
    main()
