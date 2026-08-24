from datetime import datetime, timedelta
import random
import numpy as np
from uuid import uuid4
from simulation.state.entities import User, Account, Card, Device, IP, Transaction, Campaign
from simulation.state.environment import PaymentEnvironment

class SyntheticIdentityAgent:
    def __init__(self, env: PaymentEnvironment, round_id: int = 1, strategy_params: dict = None):
        self.env = env
        self.round_id = round_id
        self.strategy_params = strategy_params or {}

    def execute_campaign(self, start_time: datetime) -> Campaign:
        # Determine highly diverse campaign parameters
        p = self.strategy_params
        seeding_count = int(max(2, np.random.normal(loc=p.get('seeding_count_loc', 12), scale=8)))
        seeding_avg_amt = max(10.0, np.random.normal(loc=p.get('seeding_avg_amt_loc', 35), scale=15))
        seeding_delay_mean_h = max(6, np.random.normal(loc=p.get('seeding_delay_loc', 36), scale=24))
        
        drift_count = int(max(1, np.random.normal(loc=p.get('drift_count_loc', 4), scale=2)))
        drift_avg_amt = max(100.0, np.random.normal(loc=p.get('drift_avg_amt_loc', 250), scale=100))
        drift_delay_mean_h = max(2, np.random.normal(loc=p.get('drift_delay_loc', 8), scale=6))
        
        fraud_count = int(max(1, np.random.normal(loc=3, scale=2)))
        fraud_avg_amt_loc_raw = p.get('fraud_avg_amt_loc', 1500)
        # Floor constraint: bust-out amount cannot drop below 3x the normal spending baseline
        fraud_avg_amt_loc = max(float(fraud_avg_amt_loc_raw), 3.0 * seeding_avg_amt)
        fraud_avg_amt = max(200.0, np.random.normal(loc=fraud_avg_amt_loc, scale=fraud_avg_amt_loc * 0.3))
        
        # Timing strategy for bust-out
        timing_strategy = p.get('timing_strategy', random.choice(["blend_peak", "off_peak", "random"]))
        
        campaign = Campaign(
            attack_type="Synthetic Identity",
            phase="init",
            objective="Build trust, then bust out",
            status="Active",
            round_id=self.round_id,
            history=[]
        )
        self.env.register_campaign(campaign)
        
        def log_action(phase: str, action: str, params: dict, t: datetime):
            campaign.phase = phase
            campaign.history.append({
                "timestamp": t.isoformat(),
                "phase": phase,
                "action": action,
                "parameters": params
            })
        
        current_time = start_time
        
        # Phase 1: Identity creation
        log_action("identity_creation", "create_user", {"is_synthetic": True}, current_time)
        user = User(created_at=current_time, is_synthetic=True)
        self.env.register_user(user)
        current_time += timedelta(hours=random.randint(1, 24))
        
        # Phase 2: Account opening
        log_action("account_opening", "open_account", {"doc_type": "synthetic"}, current_time)
        account = Account(user_id=user.user_id, opened_at=current_time)
        self.env.register_account(account)
        current_time += timedelta(hours=random.randint(1, 24))
        
        # Phase 3: Card issuance
        log_action("card_issuance", "issue_card", {"type": "virtual"}, current_time)
        card = Card(account_id=account.account_id, issued_at=current_time)
        self.env.register_card(card)
        device = Device(user_id=user.user_id, first_seen=current_time, trust_score=0.5)
        self.env.register_device(device)
        ip = IP(ip_id=f"10.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}", 
                geo="US", first_seen=current_time)
        self.env.register_ip(ip)
        current_time += timedelta(days=random.randint(1, 3))
        
        # Phase 4: Normal-looking seeding
        log_action("normal_seeding", "generate_baseline_txns", {"count": seeding_count, "avg_amount": round(seeding_avg_amt, 2)}, current_time)
        merchants_list = list(self.env.merchants.values())
        if not merchants_list: return campaign
            
        for _ in range(seeding_count):
            amount = round(max(1.0, np.random.normal(loc=seeding_avg_amt, scale=seeding_avg_amt*0.2)), 2)
            merchant = random.choice(merchants_list)
            txn = Transaction(
                account_id=account.account_id, card_id=card.card_id, device_id=device.device_id, ip_id=ip.ip_id,
                merchant_id=merchant.merchant_id, amount=amount, timestamp=current_time, channel="Online",
                label="Legit", campaign_id=campaign.campaign_id, round_id=self.round_id
            )
            self.env.process_transaction(txn)
            current_time += timedelta(hours=max(1, np.random.normal(loc=seeding_delay_mean_h, scale=seeding_delay_mean_h*0.3)))
            
        # Phase 5: Gradual drift
        log_action("gradual_drift", "increase_velocity_and_amount", {"count": drift_count, "avg_amount": round(drift_avg_amt, 2)}, current_time)
        for _ in range(drift_count):
            amount = round(max(50.0, np.random.normal(loc=drift_avg_amt, scale=drift_avg_amt*0.2)), 2)
            merchant = random.choice(merchants_list)
            txn = Transaction(
                account_id=account.account_id, card_id=card.card_id, device_id=device.device_id, ip_id=ip.ip_id,
                merchant_id=merchant.merchant_id, amount=amount, timestamp=current_time, channel="Online",
                label="Legit", campaign_id=campaign.campaign_id, round_id=self.round_id
            )
            self.env.process_transaction(txn)
            current_time += timedelta(hours=max(0.5, np.random.normal(loc=drift_delay_mean_h, scale=drift_delay_mean_h*0.3)))
            
        # Phase 6: Fraud Attempt (Bust-out)
        # Apply timing strategy
        if timing_strategy == "blend_peak":
            target_hour = random.choice(list(range(10, 21)))
        elif timing_strategy == "off_peak":
            target_hour = random.choice(list(range(0, 7)))
        else:
            target_hour = -1
            
        if target_hour != -1:
            if current_time.hour <= target_hour:
                hours_to_add = target_hour - current_time.hour
            else:
                hours_to_add = 24 - current_time.hour + target_hour
            current_time += timedelta(hours=hours_to_add, minutes=random.randint(0, 59))
            
        log_action("fraud_attempt", "bust_out", {"count": fraud_count, "avg_amount": round(fraud_avg_amt, 2), "timing_strategy": timing_strategy}, current_time)
        for _ in range(fraud_count):
            amount = round(max(200.0, np.random.normal(loc=fraud_avg_amt, scale=fraud_avg_amt*0.3)), 2)
            merchant = random.choice(merchants_list)
            txn = Transaction(
                account_id=account.account_id, card_id=card.card_id, device_id=device.device_id, ip_id=ip.ip_id,
                merchant_id=merchant.merchant_id, amount=amount, timestamp=current_time, channel="Online",
                label="Fraud", campaign_id=campaign.campaign_id, round_id=self.round_id
            )
            self.env.process_transaction(txn)
            current_time += timedelta(minutes=random.randint(2, 30))
            
        campaign.status = "Completed"
        log_action("completed", "campaign_end", {"total_fraud_txns": fraud_count}, current_time)
        return campaign

