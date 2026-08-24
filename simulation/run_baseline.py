import os
import json
import random
import pandas as pd
from datetime import datetime, timedelta
from simulation.state.environment import PaymentEnvironment
from simulation.state.baseline_generator import LegitimateTrafficGenerator
from simulation.attacks.synthetic_identity import SyntheticIdentityAgent
from simulation.attacks.account_takeover import AccountTakeoverAgent

def main():
    print("Initializing Payment World State Model...")
    start_time = datetime(2026, 1, 1, 0, 0, 0)
    env = PaymentEnvironment(start_time=start_time)
    
    # Target scale from spec: 3,000-5,000 users over 3 months
    num_users = 4000
    generator = LegitimateTrafficGenerator(env=env, num_users=num_users, num_merchants=500)
    
    print(f"Bootstrapping {num_users} users and initial entities...")
    generator.bootstrap_world()
    
    print("Generating baseline timeline (Poisson event-driven) over 90 days...")
    generator.generate_timeline(duration_days=90)
    
    print("Injecting Synthetic Identity attacks...")
    num_attacks = 400
    attack_agent = SyntheticIdentityAgent(env=env, round_id=1)
    
    campaigns = []
    for _ in range(num_attacks):
        attack_start = start_time + timedelta(days=random.randint(1, 60), hours=random.randint(0, 23))
        campaign = attack_agent.execute_campaign(start_time=attack_start)
        campaigns.append(campaign)
        
    print("Injecting Account Takeover attacks...")
    ato_agent = AccountTakeoverAgent(env=env, round_id=1)
    
    # Select legitimate users who actually have an account and card
    valid_users = [u for u in env.users.values() if not u.is_synthetic]
    for _ in range(num_attacks):
        user = random.choice(valid_users)
        account = next((a for a in env.accounts.values() if a.user_id == user.user_id), None)
        card = next((c for c in env.cards.values() if c.account_id == account.account_id), None) if account else None
        
        if account and card:
            # Random time after their account opened
            attack_start = account.opened_at + timedelta(days=random.randint(10, 60), hours=random.randint(0, 23))
            campaign = ato_agent.execute_campaign(start_time=attack_start, user=user, account=account, card=card)
            campaigns.append(campaign)
        
    print(f"Generated {len(env.transactions)} total transactions (including attacks).")
    
    # Re-sort chronologically since attacks were generated post-hoc
    env.transactions.sort(key=lambda x: x.timestamp)
    
    output_dir = "ml/data"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save all campaigns for diversity analysis
    campaigns_path = os.path.join(output_dir, "campaigns.json")
    with open(campaigns_path, "w") as f:
        def default_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            from uuid import UUID
            if isinstance(obj, UUID):
                return str(obj)
            raise TypeError(f"Type {type(obj)} not serializable")
        json.dump([c.model_dump() for c in campaigns], f, default=default_serializer, indent=2)
        
    # Keep the single sample trace as requested
    sample_campaign = campaigns[0]
    trace_path = os.path.join(output_dir, "sample_campaign_trace.json")
    with open(trace_path, "w") as f:
        json.dump(sample_campaign.model_dump(), f, default=default_serializer, indent=2)

        
    # Save to CSV
    output_path = os.path.join(output_dir, "simulated_baseline.csv")
    print(f"Saving transactions to {output_path}...")
    records = [txn.model_dump() for txn in env.transactions]
    df = pd.DataFrame(records)
    
    # Clean up non-serializable elements or UUIDs to string
    for col in df.columns:
        df[col] = df[col].astype(str)
        
    df.to_csv(output_path, index=False)
    print("Done.")

if __name__ == "__main__":
    main()
