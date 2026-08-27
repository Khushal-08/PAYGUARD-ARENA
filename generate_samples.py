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
        txn_dict = txn_obj.model_dump()
        row = {}
        for f in features:
            val = txn_dict.get(f)
            if val is None or val == "":
                if f == 'account_time_since_last_txn':
                    row[f] = np.nan
                elif f == 'is_new_account':
                    row[f] = 1.0 if txn_dict.get('account_time_since_last_txn') in (None, "") else 0.0
                else:
                    row[f] = 0.0
            else:
                row[f] = float(val)
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
        if i == 0:
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
            if i == 0:
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
            if i == 0:
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
