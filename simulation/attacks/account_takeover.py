from datetime import datetime, timedelta
import random
import numpy as np
from uuid import uuid4
from simulation.state.entities import User, Account, Card, Device, IP, Transaction, Campaign
from simulation.state.environment import PaymentEnvironment

class AccountTakeoverAgent:
    def __init__(self, env: PaymentEnvironment, round_id: int = 1):
        self.env = env
        self.round_id = round_id

    def execute_campaign(self, start_time: datetime, user: User, account: Account, card: Card) -> Campaign:
        # Determine highly diverse campaign parameters
        shift_count = int(max(1, np.random.normal(loc=2, scale=1)))
        shift_avg_amt = max(1.0, np.random.normal(loc=5, scale=3))
        shift_delay_mean_h = max(0.1, np.random.normal(loc=1.0, scale=0.5))
        
        fraud_count = int(max(2, np.random.normal(loc=5, scale=3)))
        fraud_avg_amt = max(200.0, np.random.normal(loc=2000, scale=1000))
        
        # Timing strategy for cash-out
        timing_strategy = random.choice(["immediate", "wait_for_night", "gradual_drain"])
        
        campaign = Campaign(
            attack_type="Account Takeover",
            phase="baseline_established",
            objective="Hijack account and cash out",
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
        
        # Phase 1: Baseline established (already done by legitimate generator, but we log it as the starting phase)
        log_action("baseline_established", "observe_baseline", {"user_id": str(user.user_id)}, current_time)
        current_time += timedelta(hours=random.randint(1, 48))
        
        # Phase 2: Compromise event (New Device / IP)
        log_action("compromise_event", "new_device_login", {"method": "credential_stuffing"}, current_time)
        device = Device(user_id=user.user_id, first_seen=current_time, trust_score=0.1)
        self.env.register_device(device)
        ip = IP(ip_id=f"10.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}", 
                geo="US", first_seen=current_time)
        self.env.register_ip(ip)
        
        if timing_strategy == "wait_for_night":
            current_time += timedelta(hours=random.randint(4, 12))
        else:
            current_time += timedelta(minutes=random.randint(5, 60))
            
        # Phase 3: Behavior Shift (Probing)
        merchants_list = list(self.env.merchants.values())
        if not merchants_list: return campaign
        
        log_action("behavior_shift", "probe_account", {"count": shift_count, "avg_amount": round(shift_avg_amt, 2)}, current_time)
        for _ in range(shift_count):
            amount = round(max(0.5, np.random.normal(loc=shift_avg_amt, scale=shift_avg_amt*0.2)), 2)
            merchant = random.choice(merchants_list)
            txn = Transaction(
                account_id=account.account_id, card_id=card.card_id, device_id=device.device_id, ip_id=ip.ip_id,
                merchant_id=merchant.merchant_id, amount=amount, timestamp=current_time, channel="Online",
                label="Fraud", campaign_id=campaign.campaign_id, round_id=self.round_id
            )
            self.env.process_transaction(txn)
            current_time += timedelta(hours=max(0.1, np.random.normal(loc=shift_delay_mean_h, scale=shift_delay_mean_h*0.3)))
            
        # Phase 4: Fraud Attempt (Cash-out)
        log_action("cash_out", "drain_funds", {"count": fraud_count, "avg_amount": round(fraud_avg_amt, 2), "timing_strategy": timing_strategy}, current_time)
        for _ in range(fraud_count):
            amount = round(max(50.0, np.random.normal(loc=fraud_avg_amt, scale=fraud_avg_amt*0.3)), 2)
            merchant = random.choice(merchants_list)
            txn = Transaction(
                account_id=account.account_id, card_id=card.card_id, device_id=device.device_id, ip_id=ip.ip_id,
                merchant_id=merchant.merchant_id, amount=amount, timestamp=current_time, channel="Online",
                label="Fraud", campaign_id=campaign.campaign_id, round_id=self.round_id
            )
            self.env.process_transaction(txn)
            if timing_strategy == "gradual_drain":
                current_time += timedelta(hours=random.randint(1, 4))
            else:
                current_time += timedelta(minutes=random.randint(1, 10))
                
        campaign.status = "Completed"
        log_action("completed", "campaign_end", {"total_fraud_txns": shift_count + fraud_count}, current_time)
        return campaign
