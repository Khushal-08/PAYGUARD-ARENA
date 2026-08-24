import os
import sys
import random
from uuid import uuid4
import pandas as pd
from datetime import datetime, timedelta
from xgboost import XGBClassifier

# Ensure the correct path is used
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simulation.state.environment import PaymentEnvironment
from simulation.state.entities import User, Account, Card, Transaction, Device, IP, Merchant
from simulation.attacks.genai_social_engineering import SocialEngineeringAgent
from ml.features.entity_aggregates import engineer_all_entity_features

import pickle

def load_defense_model():
    print("Loading locked defense model (round 1)...")
    with open("ml/models/xgboost_baseline_round_1.pkl", "rb") as f:
        clf = pickle.load(f)
    
    features = ['amount', 'hour_of_day', 'day_of_week', 'account_time_since_last_txn', 
                'is_new_account', 'account_txns_24h', 'account_txns_7d', 'device_txns_7d', 
                'is_familiar_merchant']
    return clf, features

def main():
    # 1. Load Defense Model
    defense_model, feature_cols = load_defense_model()

    print("\nInitializing environment...")
    env = PaymentEnvironment(start_time=datetime.now() - timedelta(days=90))
    
    merchants = [
        Merchant(name="Amazon", category="Retail", risk_score=0.1),
        Merchant(name="Netflix", category="Entertainment", risk_score=0.1),
        Merchant(name="Local Grocery", category="Groceries", risk_score=0.2),
        Merchant(name="Uber", category="Transport", risk_score=0.3)
    ]
    for m in merchants:
        env.register_merchant(m)
        
    num_campaigns = 150
    print(f"\n=== EXECUTING ATTACK 3: {num_campaigns} CAMPAIGNS ===")
    
    agent = SocialEngineeringAgent(env, round_id=1)
    
    authorized_count = 0
    total_score = 0
    authorized_txns = []
    
    # Store the first victim for diversity check
    first_user = None
    first_account = None
    first_card = None
    
    for i in range(num_campaigns):
        # Create a legitimate user
        user = User(created_at=datetime.now() - timedelta(days=90), is_synthetic=False)
        env.register_user(user)
        account = Account(user_id=user.user_id, opened_at=user.created_at)
        env.register_account(account)
        card = Card(account_id=account.account_id, issued_at=user.created_at)
        env.register_card(card)
        dev = Device(user_id=user.user_id, first_seen=user.created_at, trust_score=0.9)
        env.register_device(dev)
        ip = IP(ip_id=f"192.168.1.{i+2}", geo="US", first_seen=user.created_at)
        env.register_ip(ip)
        
        # Save first user for diversity check later
        if i == 0:
            first_user, first_account, first_card = user, account, card
            
        # Generate some legitimate transactions for the victim to build a profile
        current_time = datetime.now() - timedelta(days=30)
        for _ in range(15):
            m = merchants[0] if random.random() > 0.5 else merchants[2]
            amt = random.uniform(20.0, 150.0)
            t = current_time + timedelta(hours=random.randint(18, 22), minutes=random.randint(0, 59))
            txn = Transaction(
                account_id=account.account_id, card_id=card.card_id, device_id=dev.device_id, ip_id=ip.ip_id,
                merchant_id=m.merchant_id, amount=amt, timestamp=t, channel="Online", label="Legit",
                campaign_id=None, round_id=0
            )
            env.process_transaction(txn)
            current_time += timedelta(days=random.randint(1, 3))
            
        start_t = datetime.now()
        campaign = agent.execute_campaign(start_t, user, account, card)
        
        scenario_history = next((h for h in campaign.history if h['phase'] == 'scenario_generation' and h['action'] == 'scenario_created'), None)
        if scenario_history:
            scenario = scenario_history['parameters']
            total_score += scenario.get('persuasiveness_score', 0)
            
        if campaign.status == "Completed":
            authorized_count += 1
            # Get the fraudulent transaction that was just appended to the environment
            txn = [t for t in env.transactions if t.campaign_id == campaign.campaign_id and t.label == "Fraud"][-1]
            authorized_txns.append(txn)

    # Diversity check
    print(f"\n--- Diversity Check (3 campaigns targeting same profile) ---")
    for j in range(3):
        camp = agent.execute_campaign(datetime.now(), first_user, first_account, first_card)
        scenario_history = next((h for h in camp.history if h['phase'] == 'scenario_generation' and h['action'] == 'scenario_created'), None)
        if scenario_history:
            print(f"Scenario {j+1}: {scenario_history['parameters']}")

    print("\n=== SUMMARY STATS ===")
    print(f"Total Campaigns Generated: {num_campaigns}")
    print(f"Authorization Rate: {authorized_count / num_campaigns * 100:.2f}% ({authorized_count} authorized)")
    print(f"Average Persuasiveness Score: {total_score / num_campaigns:.2f}/10")
    
    if authorized_txns:
        # Score authorized transactions against defense model
        # We need to construct a dataframe of these transactions to engineer features
        print("\nEvaluating authorized transactions against the Defense Model...")
        # To get the right features, we have to engineer them in the context of the user's history
        # Our `env` has the history for these users. Let's dump all `env` txns to a DataFrame
        all_txns_dicts = []
        for t in env.transactions:
            all_txns_dicts.append({
                'transaction_id': t.transaction_id,
                'account_id': t.account_id,
                'device_id': t.device_id,
                'merchant_id': t.merchant_id,
                'timestamp': t.timestamp,
                'amount': t.amount,
                'label': t.label,
                'campaign_id': t.campaign_id
            })
        env_df = pd.DataFrame(all_txns_dicts)
        env_df = engineer_all_entity_features(env_df)
        env_df['hour_of_day'] = env_df['timestamp'].dt.hour
        env_df['day_of_week'] = env_df['timestamp'].dt.dayofweek
        
        # Filter down to the authorized attacks
        fraud_df = env_df[env_df['label'] == 'Fraud'].copy()
        
        X_fraud = fraud_df[feature_cols].fillna(0)
        preds = defense_model.predict_proba(X_fraud)[:, 1]
        
        threshold = 0.5
        detected_count = sum(p >= threshold for p in preds)
        
        print(f"Defense Model Detection Rate (Threshold {threshold}): {detected_count / len(preds) * 100:.2f}% ({detected_count} out of {len(preds)} detected)")
        print(f"Average Predicted Fraud Probability: {preds.mean():.4f}")
    else:
        print("\nNo campaigns were authorized, cannot evaluate defense model.")

if __name__ == '__main__':
    main()
